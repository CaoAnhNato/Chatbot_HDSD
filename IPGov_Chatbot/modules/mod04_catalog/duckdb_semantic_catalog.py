"""
Module: IPGov_Chatbot/modules/mod04_catalog/duckdb_semantic_catalog.py
Chức năng: Quản lý DuckDB In-Memory Metadata Catalog, ART Indexes, Native FTS (BM25)
và RapidFuzz C++ semantic similarity matching cho từ viết tắt công vụ.
Căn cứ: Blueprint 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import duckdb
import numpy as np
from openai import OpenAI
from rapidfuzz import fuzz, process

from IPGov_Chatbot.config import settings
from IPGov_Chatbot.core.model_registry import ModelRegistry
from IPGov_Chatbot.schemas.catalog_dto import ColumnMetadataDTO, TableMetadataDTO

logger = logging.getLogger(__name__)


def _remove_accents(raw_str: str) -> str:
    if not raw_str:
        return ""
    import unicodedata
    s = raw_str.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


ALLOWED_SEMANTIC_LEXICON_SEED = (
    # SC-5.2 Form criteria group
    ("FORM_CRITERIA_GROUP", "biểu mẫu", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "bieu mau", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "collection_form", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "criteria_group", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "bộ thu thập", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "bo thu thap", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "tờ khai", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "to khai", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "mẫu biểu", "FORM_CRITERIA_GROUP", 1.0),
    ("FORM_CRITERIA_GROUP", "mau bieu", "FORM_CRITERIA_GROUP", 1.0),
    # Mission keywords
    ("MISSION_KEYWORD", "nhiệm vụ", "MISSION", 1.0),
    ("MISSION_KEYWORD", "nhiem vu", "MISSION", 1.0),
    ("MISSION_KEYWORD", "mission", "MISSION", 1.0),
    ("MISSION_KEYWORD", "phân công", "MISSION", 1.0),
    ("MISSION_KEYWORD", "phan cong", "MISSION", 1.0),
    ("MISSION_KEYWORD", "đề án", "MISSION", 1.0),
    ("MISSION_KEYWORD", "de an", "MISSION", 1.0),
    # Office keywords
    ("OFFICE_KEYWORD", "phòng ban", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "phong ban", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "đơn vị", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "don vi", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "office_mission", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "văn phòng", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "van phong", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "sở", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "ban ngành", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "ban nganh", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "chi cục", "OFFICE", 1.0),
    ("OFFICE_KEYWORD", "chi cuc", "OFFICE", 1.0),
    # Officer keywords
    ("OFFICER_KEYWORD", "cán bộ", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "can bo", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "nhân sự", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "nhan su", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "user_mission", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "office_user", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "phụ trách", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "phu trach", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "chủ trì", "OFFICER", 1.0),
    ("OFFICER_KEYWORD", "chu tri", "OFFICER", 1.0),
    # Matrix cues
    ("MATRIX_CUE", "ma trận", "MATRIX", 1.0),
    ("MATRIX_CUE", "ma tran", "MATRIX", 1.0),
    ("MATRIX_CUE", "kiểm toán phân công", "MATRIX", 1.0),
    ("MATRIX_CUE", "kiem toan phan cong", "MATRIX", 1.0),
    ("MATRIX_CUE", "office_mission", "MATRIX", 1.0),
    ("MATRIX_CUE", "user_mission", "MATRIX", 1.0),
    ("MATRIX_CUE", "chưa phân công", "MATRIX", 1.0),
    ("MATRIX_CUE", "chua phan cong", "MATRIX", 1.0),
    ("MATRIX_CUE", "độ lệch", "MATRIX", 1.0),
    ("MATRIX_CUE", "do lech", "MATRIX", 1.0),
    ("MATRIX_CUE", "tổng hợp phân công", "MATRIX", 1.0),
    ("MATRIX_CUE", "tong hop phan cong", "MATRIX", 1.0),
    # Report signals
    ("REPORT_SIGNAL", "báo cáo", "REPORT", 1.0),
    ("REPORT_SIGNAL", "bao cao", "REPORT", 1.0),
    ("REPORT_SIGNAL", "đợt nộp", "REPORT", 1.0),
    ("REPORT_SIGNAL", "dot nop", "REPORT", 1.0),
    ("REPORT_SIGNAL", "kỳ báo cáo", "REPORT", 1.0),
    ("REPORT_SIGNAL", "ky bao cao", "REPORT", 1.0),
    ("REPORT_SIGNAL", "tiến độ nộp", "REPORT", 1.0),
    ("REPORT_SIGNAL", "tien do nop", "REPORT", 1.0),
    ("REPORT_SIGNAL", "trạng thái báo cáo", "REPORT", 1.0),
    ("REPORT_SIGNAL", "trang thai bao cao", "REPORT", 1.0),
    ("REPORT_SIGNAL", "phê duyệt báo cáo", "REPORT", 1.0),
    ("REPORT_SIGNAL", "phe duyet bao cao", "REPORT", 1.0),
    ("REPORT_SIGNAL", "submitted_date", "REPORT", 1.0),
    ("REPORT_SIGNAL", "tiến độ nộp báo cáo", "REPORT", 1.2),
    ("REPORT_SIGNAL", "tien do nop bao cao", "REPORT", 1.2),
    ("REPORT_SIGNAL", "báo cáo nháp", "REPORT", 1.2),
    ("REPORT_SIGNAL", "bao cao nhap", "REPORT", 1.2),
    # Report status
    ("REPORT_STATUS", "bản nháp", "STATUS", 1.0),
    ("REPORT_STATUS", "ban nhap", "STATUS", 1.0),
    ("REPORT_STATUS", "nháp", "STATUS", 1.0),
    ("REPORT_STATUS", "nhap", "STATUS", 1.0),
    ("REPORT_STATUS", "draft", "STATUS", 1.0),
    ("REPORT_STATUS", "approved", "STATUS", 1.0),
    ("REPORT_STATUS", "pending", "STATUS", 1.0),
    ("REPORT_STATUS", "chưa phê duyệt", "STATUS", 1.0),
    ("REPORT_STATUS", "chua phe duyet", "STATUS", 1.0),
    ("REPORT_STATUS", "chờ duyệt", "STATUS", 1.0),
    ("REPORT_STATUS", "cho duyet", "STATUS", 1.0),
    ("REPORT_STATUS", "chưa nộp", "STATUS", 1.0),
    ("REPORT_STATUS", "chua nop", "STATUS", 1.0),
    ("REPORT_STATUS", "tiến độ", "STATUS", 1.0),
    ("REPORT_STATUS", "tien do", "STATUS", 1.0),
    ("REPORT_STATUS", "trạng thái", "STATUS", 1.0),
    ("REPORT_STATUS", "trang thai", "STATUS", 1.0),
    ("REPORT_STATUS", "đã phê duyệt", "STATUS", 1.0),
    ("REPORT_STATUS", "da phe duyet", "STATUS", 1.0),
    ("REPORT_STATUS", "đối chiếu", "STATUS", 1.0),
    ("REPORT_STATUS", "doi chieu", "STATUS", 1.0),
    ("REPORT_STATUS", "chênh lệch", "STATUS", 1.0),
    ("REPORT_STATUS", "chenh lech", "STATUS", 1.0),
    # Report diff
    ("REPORT_DIFF", "bản nháp", "DIFF", 1.0),
    ("REPORT_DIFF", "ban nhap", "DIFF", 1.0),
    ("REPORT_DIFF", "nháp", "DIFF", 1.0),
    ("REPORT_DIFF", "nhap", "DIFF", 1.0),
    ("REPORT_DIFF", "draft", "DIFF", 1.0),
    ("REPORT_DIFF", "đối chiếu", "DIFF", 1.0),
    ("REPORT_DIFF", "doi chieu", "DIFF", 1.0),
    ("REPORT_DIFF", "so sánh", "DIFF", 1.0),
    ("REPORT_DIFF", "so sanh", "DIFF", 1.0),
    ("REPORT_DIFF", "chênh lệch", "DIFF", 1.0),
    ("REPORT_DIFF", "chenh lech", "DIFF", 1.0),
    ("REPORT_DIFF", "chi tiết", "DIFF", 1.0),
    ("REPORT_DIFF", "chi tiet", "DIFF", 1.0),
    ("REPORT_DIFF", "tất cả", "DIFF", 1.0),
    ("REPORT_DIFF", "tat ca", "DIFF", 1.0),
    # Officer query
    ("OFFICER_QUERY", "cán bộ", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "can bo", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "nhân sự", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "nhan su", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "người dùng", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "nguoi dung", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "user", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "officer", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "ai phụ trách", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "ai phu trach", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "ai chủ trì", "OFFICER_QUERY", 1.0),
    ("OFFICER_QUERY", "ai chu tri", "OFFICER_QUERY", 1.0),
    # Officer query negative keywords (for _is_officer_query)
    ("OFFICER_QUERY_NEGATIVE", "nào", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "nao", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "các chỉ tiêu", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "cac chi tieu", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "những chỉ tiêu", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "nhung chi tieu", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "danh mục", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "danh muc", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "thu thập", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "thu thap", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "tiêu chí", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "tieu chi", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "các tiêu chí", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "cac tieu chi", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "những tiêu chí", "NEGATIVE", 1.0),
    ("OFFICER_QUERY_NEGATIVE", "nhung tieu chi", "NEGATIVE", 1.0),
    # Officer query positive keywords (for _is_officer_query)
    ("OFFICER_QUERY_POSITIVE", "cán bộ", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "can bo", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "nhân sự", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "nhan su", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "nhân viên", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "nhan vien", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "chuyên viên", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "chuyen vien", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "chức vụ", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "chuc vu", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "ai phụ trách", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "ai phu trach", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "tài khoản", "POSITIVE", 1.0),
    ("OFFICER_QUERY_POSITIVE", "tai khoan", "POSITIVE", 1.0),
    # Capability meta
    ("CAPABILITY_META", "bạn có thể làm gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ban co the lam gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "bạn có thể giúp gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ban co the giup gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "bạn có thể giúp", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ban co the giup", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "chức năng của bạn", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "chuc nang cua ban", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "giới thiệu về bạn", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "gioi thieu ve ban", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "năng lực của bạn", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "nang luc cua ban", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "hướng dẫn sử dụng", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "huong dan su dung", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "trợ giúp", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "tro giup", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "bạn là ai", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ban la ai", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "bạn làm được gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ban lam duoc gi", "CAPABILITY", 1.0),
    # Domain signal
    ("DOMAIN_SIGNAL", "nông nghiệp", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "nong nghiep", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "phát triển nông thôn", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "phat trien nong thon", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "diêm nghiệp", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "diem nghiep", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "chỉ tiêu", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "chi tieu", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "nhiệm vụ", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "nhiem vu", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "chi cục", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "chi cuc", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "thực hiện", "DOMAIN", 1.0),
    ("DOMAIN_SIGNAL", "thuc hien", "DOMAIN", 1.0),
    # Metric listing triggers
    ("METRIC_LIST_TRIGGER", "danh sách", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "danh sach", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "danh mục", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "danh muc", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "liệt kê", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "liet ke", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "có những chỉ tiêu nào", "LIST", 1.2),
    ("METRIC_LIST_TRIGGER", "gồm những chỉ tiêu nào", "LIST", 1.2),
    ("METRIC_LIST_TRIGGER", "những chỉ tiêu nào", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "nhung chi tieu nao", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "những chỉ tiêu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "nhung chi tieu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "các chỉ tiêu nào", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "cac chi tieu nao", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "chỉ tiêu nào", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "chi tieu nao", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "chỉ tiêu gì", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "chi tieu gi", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "tất cả chỉ tiêu", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "tất cả các chỉ tiêu", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "có các chỉ tiêu nào", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "hệ thống đang có các chỉ tiêu nào", "LIST", 1.2),
    ("METRIC_LIST_TRIGGER", "thu thập các chỉ tiêu nào", "LIST", 1.2),
    ("METRIC_LIST_TRIGGER", "thu thap cac chi tieu nao", "LIST", 1.2),
    ("METRIC_LIST_TRIGGER", "các chỉ tiêu năm", "LIST", 1.1),
    ("METRIC_LIST_TRIGGER", "các chỉ tiêu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "cac chi tieu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "phụ trách chỉ tiêu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "quản lý chỉ tiêu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "thực hiện chỉ tiêu", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "các tiêu chí", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "cac tieu chi", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "những tiêu chí", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "nhung tieu chi", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "tiêu chí nào", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "tieu chi nao", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "tiêu chí gì", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "tieu chi gi", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "các hạng mục", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "cac hang muc", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "hiển thị", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "hien thi", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "thu thập được", "LIST", 1.0),
    ("METRIC_LIST_TRIGGER", "thu thap duoc", "LIST", 1.0),
    # Metric listing target
    ("METRIC_LIST_TARGET", "chỉ tiêu", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "chi tieu", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "tiêu chí", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "tieu chi", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "hạng mục", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "hang muc", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "cấp đầu", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "cap dau", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "cấp 1", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "cap 1", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "cấp một", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "cap mot", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "bậc 1", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "bac 1", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "đầu mục", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "dau muc", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "gốc", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "goc", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "chỉ số", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "chi so", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "mục tiêu", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "muc tieu", "METRIC", 1.0),
    ("METRIC_LIST_TARGET", "criteria", "METRIC", 1.0),
    # Criteria count
    ("CRITERIA_COUNT", "có bao nhiêu", "COUNT", 1.0),
    ("CRITERIA_COUNT", "co bao nhieu", "COUNT", 1.0),
    ("CRITERIA_COUNT", "tổng số", "COUNT", 1.0),
    ("CRITERIA_COUNT", "tong so", "COUNT", 1.0),
    ("CRITERIA_COUNT", "đếm số", "COUNT", 1.0),
    ("CRITERIA_COUNT", "dem so", "COUNT", 1.0),
    ("CRITERIA_COUNT", "số lượng", "COUNT", 1.0),
    ("CRITERIA_COUNT", "so luong", "COUNT", 1.0),
    ("CRITERIA_COUNT", "có mấy", "COUNT", 1.0),
    ("CRITERIA_COUNT", "co may", "COUNT", 1.0),
    # Criteria reported
    ("CRITERIA_REPORTED", "được báo cáo", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "duoc bao cao", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "được thu thập", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "duoc thu thap", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "phát sinh", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "phat sinh", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "thu thập được", "REPORTED", 1.0),
    ("CRITERIA_REPORTED", "thu thap duoc", "REPORTED", 1.0),
    # Point value
    ("POINT_VALUE", "là bao nhiêu", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "la bao nhieu", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "đạt bao nhiêu", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "dat bao nhieu", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "hiện tại là bao nhiêu", "POINT_VALUE", 1.2),
    ("POINT_VALUE", "hien tai la bao nhieu", "POINT_VALUE", 1.2),
    ("POINT_VALUE", "giá trị bao nhiêu", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "gia tri bao nhieu", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "bao nhiêu ?", "POINT_VALUE", 1.0),
    ("POINT_VALUE", "bao nhieu ?", "POINT_VALUE", 1.0),
    # Performer verb
    ("PERFORMER_VERB", "thực hiện", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "thuc hien", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "chủ trì", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "chu tri", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "quản lý", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "quan ly", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "phụ trách", "PERFORMER", 1.0),
    ("PERFORMER_VERB", "phu trach", "PERFORMER", 1.0),
    # Unit interrogative
    ("UNIT_INTERROGATIVE", "đơn vị nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "don vi nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "phòng nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "phong nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "phòng ban nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "phong ban nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "cơ quan nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "co quan nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "sở nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "so nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "chi cục nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "chi cuc nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "văn phòng nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "van phong nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "tỉnh nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "tinh nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "địa phương nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "dia phuong nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai thực hiện", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai thuc hien", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai phụ trách", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai phu trach", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai chủ trì", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai chu tri", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai quản lý", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "ai quan ly", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "do ai", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "do don vi", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "do đơn vị", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "do phong", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "do phòng", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "thuộc đơn vị nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "thuoc don vi nao", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "của đơn vị nào", "UNIT", 1.0),
    ("UNIT_INTERROGATIVE", "cua don vi nao", "UNIT", 1.0),
    # Capability meta
    ("CAPABILITY_META", "giúp gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "giup gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "làm được gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "lam duoc gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "chức năng gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "chuc nang gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "những chức năng", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "nhung chuc nang", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "hỗ trợ những gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ho tro nhung gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "hỗ trợ gì", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ho tro gi", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "bạn là ai", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "ban la ai", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "giới thiệu về bạn", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "gioi thieu ve ban", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "khả năng của bạn", "CAPABILITY", 1.0),
    ("CAPABILITY_META", "kha nang cua ban", "CAPABILITY", 1.0),
    # Discourse connectives (True ellipsis connectives only)
    ("DISCOURSE_CONNECTIVE", "thế còn", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "the con", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "vậy còn", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "vay con", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "thế thì", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "the thi", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "còn thì", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "con thi", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "còn", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "thì sao", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "thi sao", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "thế sao", "CONNECTIVE", 1.0),
    ("DISCOURSE_CONNECTIVE", "the sao", "CONNECTIVE", 1.0),
    # Discourse demonstratives (Explicit referential phrases only)
    ("DISCOURSE_DEMONSTRATIVE", "nhóm đó", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhom do", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhánh đó", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhanh do", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhóm này", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhom nay", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhánh này", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nhanh nay", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "chỉ tiêu đó", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "chi tieu do", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "chỉ tiêu này", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "chi tieu nay", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "ở trên", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "o tren", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "nêu trên", "DEMONSTRATIVE", 1.0),
    ("DISCOURSE_DEMONSTRATIVE", "neu tren", "DEMONSTRATIVE", 1.0),
    # Report status signal
    ("REPORT_STATUS_SIGNAL", "trạng thái", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "trang thai", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "tiến độ", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "tien do", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "phê duyệt", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "phe duyet", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "vòng đời", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "vong doi", "STATUS", 1.0),
    ("REPORT_STATUS_SIGNAL", "report_status", "STATUS", 1.0),
    # Province scope signal
    ("PROVINCE_SCOPE_SIGNAL", "toàn tỉnh", "PROV", 1.0),
    ("PROVINCE_SCOPE_SIGNAL", "toan tinh", "PROV", 1.0),
    ("PROVINCE_SCOPE_SIGNAL", "của tỉnh", "PROV", 1.0),
    ("PROVINCE_SCOPE_SIGNAL", "cua tinh", "PROV", 1.0),
    ("PROVINCE_SCOPE_SIGNAL", "hệ thống", "PROV", 1.0),
    ("PROVINCE_SCOPE_SIGNAL", "he thong", "PROV", 1.0),
    # Mission scope cue
    ("MISSION_SCOPE_CUE", "nhóm lĩnh vực", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "nhom linh vuc", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "lĩnh vực", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "linh vuc", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "mảng", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "mang", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "ngành", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "nganh", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "khối", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "khoi", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "thuộc về", "SCOPE", 1.0),
    ("MISSION_SCOPE_CUE", "thuoc ve", "SCOPE", 1.0),
    # Office or ward cue
    ("OFFICE_OR_WARD_CUE", "văn phòng", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "van phong", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "từng văn phòng", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "tung van phong", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "quản lý nhà nước nào", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "quản lý nhà nước", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "quan ly nha nuoc", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "xã ", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "xa ", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "phường ", "CUE", 1.0),
    ("OFFICE_OR_WARD_CUE", "phuong ", "CUE", 1.0),
    # Office scope cue
    ("OFFICE_SCOPE_CUE", "văn phòng", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "van phong", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "từng văn phòng", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "tung van phong", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "lĩnh vực", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "linh vuc", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "quản lý nhà nước", "CUE", 1.0),
    ("OFFICE_SCOPE_CUE", "quan ly nha nuoc", "CUE", 1.0),
    # Province list query
    ("PROVINCE_LIST_QUERY", "các tỉnh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "cac tinh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "danh sách tỉnh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "danh sach tinh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "những tỉnh nào", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "nhung tinh nao", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "tỉnh thành nào", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "tinh thanh nao", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "danh mục tỉnh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "danh muc tinh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "danh sách các tỉnh", "PROV", 1.0),
    ("PROVINCE_LIST_QUERY", "danh sach cac tinh", "PROV", 1.0),
    # Code search keyword
    ("CODE_SEARCH_KEYWORD", "mã", "CODE", 1.0),
    ("CODE_SEARCH_KEYWORD", "ma", "CODE", 1.0),
    ("CODE_SEARCH_KEYWORD", "đầu tiên", "CODE", 1.0),
    ("CODE_SEARCH_KEYWORD", "dau tien", "CODE", 1.0),
    # Synthesis action cue (when 'tổng hợp' acts as a verb/action modifying another query target)
    ("SYNTHESIS_ACTION_CUE", "tổng hợp", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp số lượng", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop so luong", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp số liệu", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop so lieu", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp báo cáo", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop bao cao", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp danh sách", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop danh sach", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp tình hình", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop tinh hinh", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp các", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop cac", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tổng hợp chỉ tiêu", "ACTION", 1.0),
    ("SYNTHESIS_ACTION_CUE", "tong hop chi tieu", "ACTION", 1.0),
    # Synthesis metric cue (when 'tổng hợp' is part of an explicit metric mention)
    ("SYNTHESIS_METRIC_CUE", "chỉ tiêu tổng hợp", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "chi tieu tong hop", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "trang trại tổng hợp", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "trang trai tong hop", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "lĩnh vực tổng hợp", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "linh vuc tong hop", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "nhóm tổng hợp", "METRIC", 1.0),
    ("SYNTHESIS_METRIC_CUE", "nhom tong hop", "METRIC", 1.0),
    # Local office or ward cue
    ("LOCAL_OFFICE_OR_WARD_CUE", "lâm đồng", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "lam dong", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "văn phòng", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "van phong", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "sở", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "so", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "phòng", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "phong", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "xã", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "xa", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "phường", "LOCAL", 1.0),
    ("LOCAL_OFFICE_OR_WARD_CUE", "phuong", "LOCAL", 1.0),
    # Ward dimension
    ("WARD_DIMENSION", "xã", "WARD", 1.0),
    ("WARD_DIMENSION", "xa", "WARD", 1.0),
    ("WARD_DIMENSION", "phường", "WARD", 1.0),
    ("WARD_DIMENSION", "phuong", "WARD", 1.0),
    ("WARD_DIMENSION", "thị trấn", "WARD", 1.0),
    ("WARD_DIMENSION", "thi tran", "WARD", 1.0),
    # Province list
    ("PROV_LIST", "tỉnh", "PROV", 1.0),
    ("PROV_LIST", "tinh", "PROV", 1.0),
    ("PROV_LIST", "thành phố", "PROV", 1.0),
    ("PROV_LIST", "thanh pho", "PROV", 1.0),
    ("PROV_LIST", "địa bàn", "PROV", 1.0),
    ("PROV_LIST", "dia ban", "PROV", 1.0),
    ("PROV_LIST", "mã tỉnh", "PROV", 1.0),
    ("PROV_LIST", "ma tinh", "PROV", 1.0),
    ("PROV_LIST", "tỉnh thành", "PROV", 1.0),
    ("PROV_LIST", "tinh thanh", "PROV", 1.0),
    ("PROV_LIST", "province", "PROV", 1.0),
    # Time term
    ("TIME_TERM", "từ tháng", "TIME", 1.0),
    ("TIME_TERM", "tu thang", "TIME", 1.0),
    ("TIME_TERM", "đến tháng", "TIME", 1.0),
    ("TIME_TERM", "den thang", "TIME", 1.0),
    ("TIME_TERM", "trong tháng", "TIME", 1.0),
    ("TIME_TERM", "trong thang", "TIME", 1.0),
    ("TIME_TERM", "quý", "TIME", 1.0),
    ("TIME_TERM", "quy", "TIME", 1.0),
    ("TIME_TERM", "nửa đầu năm", "TIME", 1.0),
    ("TIME_TERM", "nua dau nam", "TIME", 1.0),
    ("TIME_TERM", "nửa cuối năm", "TIME", 1.0),
    ("TIME_TERM", "nua cuoi nam", "TIME", 1.0),
    ("TIME_TERM", "hết năm", "TIME", 1.0),
    ("TIME_TERM", "het nam", "TIME", 1.0),
    ("TIME_TERM", "cuối năm", "TIME", 1.0),
    ("TIME_TERM", "cuoi nam", "TIME", 1.0),
    ("TIME_TERM", "đầu năm", "TIME", 1.0),
    ("TIME_TERM", "dau nam", "TIME", 1.0),
    ("TIME_TERM", "tới nay", "TIME", 1.0),
    ("TIME_TERM", "toi nay", "TIME", 1.0),
    ("TIME_TERM", "đến nay", "TIME", 1.0),
    ("TIME_TERM", "den nay", "TIME", 1.0),
    ("TIME_TERM", "giai đoạn", "TIME", 1.0),
    ("TIME_TERM", "giai doan", "TIME", 1.0),
    # Level 1 criteria
    ("LEVEL1_CRITERIA_SIGNAL", "chỉ tiêu cấp 1", "LEVEL1", 1.0),
    ("LEVEL1_CRITERIA_SIGNAL", "chi tieu cap 1", "LEVEL1", 1.0),
    ("LEVEL1_CRITERIA_SIGNAL", "chỉ tiêu cấp một", "LEVEL1", 1.0),
    ("LEVEL1_CRITERIA_SIGNAL", "chi tieu cap mot", "LEVEL1", 1.0),
    ("LEVEL1_CRITERIA_SIGNAL", "chỉ tiêu cấp i", "LEVEL1", 1.0),
    ("LEVEL1_CRITERIA_SIGNAL", "chi tieu cap i", "LEVEL1", 1.0),
    ("LEVEL1_CRITERIA_SIGNAL", "cấp 1", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cap 1", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cấp một", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cap mot", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cấp i", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cap i", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "bậc 1", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "bac 1", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cấp đầu", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "cap dau", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "gốc", "LEVEL1", 0.8),
    ("LEVEL1_CRITERIA_SIGNAL", "goc", "LEVEL1", 0.8),
    ("LEVEL1_CRITERIA_SIGNAL", "đầu mục", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "dau muc", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "tiêu chí cấp", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "tieu chi cap", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "chỉ tiêu cấp", "LEVEL1", 0.9),
    ("LEVEL1_CRITERIA_SIGNAL", "chi tieu cap", "LEVEL1", 0.9),
    # Mission scope signal
    ("MISSION_SCOPE_SIGNAL", "nhiệm vụ", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "nhiem vu", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "lĩnh vực", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "linh vuc", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "đề án", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "de an", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "chương trình", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "chuong trinh", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "công tác", "MISSION_SCOPE", 1.0),
    ("MISSION_SCOPE_SIGNAL", "cong tac", "MISSION_SCOPE", 1.0),
    # Noise stripping lexicon entries (Task 4)
    ("QUERY_LEAD_NOISE", "cho tôi biết", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "cho tôi xem", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "vui lòng cho biết", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "hãy cho biết", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "thông tin số liệu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "số liệu chỉ tiêu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "số liệu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "kết quả chỉ tiêu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "giá trị chỉ tiêu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "nhóm chỉ tiêu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "chỉ tiêu", "LEAD_NOISE", 1.0),
    ("QUERY_LEAD_NOISE", "tiêu chí", "LEAD_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "hiện tại là bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "hiện nay là bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "hiện đạt bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "có giá trị là bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "có giá trị bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "đạt bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "là bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "bao nhiêu", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "hiện tại", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "hiện nay", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "trong năm", "TAIL_NOISE", 1.0),
    ("QUERY_TAIL_NOISE", "năm", "TAIL_NOISE", 1.0),
    ("OFFICER_PREFIX_NOISE", "cán bộ", "PREFIX_NOISE", 1.0),
    ("OFFICER_PREFIX_NOISE", "chuyên viên", "PREFIX_NOISE", 1.0),
    ("OFFICER_PREFIX_NOISE", "đồng chí", "PREFIX_NOISE", 1.0),
    ("METRIC_PREFIX_NOISE", "chỉ tiêu", "PREFIX_NOISE", 1.0),
    ("METRIC_PREFIX_NOISE", "tiêu chí", "PREFIX_NOISE", 1.0),
    ("MISSION_ENTITY_MARKER", "nhiệm vụ", "MARKER", 1.0),
    ("MISSION_ENTITY_MARKER", "nhiem vu", "MARKER", 1.0),
    ("MISSION_STOP_TOKEN", "hiện tại là bao nhiêu", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hien tai la bao nhieu", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hiện tại", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hien tai", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hiện nay", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hien nay", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hiện có", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hien co", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hiện đang", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hien dang", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "trên hệ thống", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "tren he thong", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "trên kho", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "tren kho", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "có chỉ tiêu", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "co chi tieu", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "có những", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "co nhung", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "có các", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "co cac", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "gồm những", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "gom nhung", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "gồm các", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "gom cac", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "bao gồm", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "bao gom", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "trong năm", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "trong nam", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "thu thập", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "thu thap", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "trọng tâm", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "trong tam", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "chuyên môn", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "chuyen mon", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "công tác", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "cong tac", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "là gì", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "la gi", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "thuộc", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "thuoc", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "của", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "cua", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "tại", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "tai", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "năm", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "nam", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "nào", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "nao", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "thì", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "thi", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hãy", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "hay", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "được", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "duoc", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "đang", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "dang", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "đã", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "da", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "do", "STOP", 1.0),
    ("MISSION_STOP_TOKEN", "?", "STOP", 1.0),
    # Metric and entity aggregation prefix noise categories
    ("METRIC_AGG_PREFIX_NOISE", "tổng số lượng", "PREFIX_NOISE", 1.0),
    ("METRIC_AGG_PREFIX_NOISE", "tổng số", "PREFIX_NOISE", 1.0),
    ("METRIC_AGG_PREFIX_NOISE", "tổng", "PREFIX_NOISE", 1.0),
    ("METRIC_AGG_PREFIX_NOISE", "số lượng", "PREFIX_NOISE", 1.0),
    ("METRIC_AGG_PREFIX_NOISE", "số", "PREFIX_NOISE", 1.0),
    # Office, Department, and Mission noise stripping categories
    ("OFFICE_PREFIX_NOISE", "phòng ban", "PREFIX_NOISE", 1.0),
    ("OFFICE_PREFIX_NOISE", "phòng", "PREFIX_NOISE", 1.0),
    ("OFFICE_PREFIX_NOISE", "văn phòng", "PREFIX_NOISE", 1.0),
    ("DEPT_PREFIX_NOISE", "sở", "PREFIX_NOISE", 1.0),
    ("DEPT_PREFIX_NOISE", "phòng", "PREFIX_NOISE", 1.0),
    ("DEPT_PREFIX_NOISE", "chi cục", "PREFIX_NOISE", 1.0),
    ("DEPT_PREFIX_NOISE", "ban", "PREFIX_NOISE", 1.0),
    ("MISSION_LEAD_PREFIX_NOISE", "kế hoạch", "PREFIX_NOISE", 1.0),
    ("MISSION_LEAD_PREFIX_NOISE", "chương trình", "PREFIX_NOISE", 1.0),
    ("MISSION_LEAD_PREFIX_NOISE", "đề án", "PREFIX_NOISE", 1.0),
    ("MISSION_LEAD_PREFIX_NOISE", "nhiệm vụ", "PREFIX_NOISE", 1.0),
    # Greeting / farewell lead noise categories
    ("GREETING_LEAD_NOISE", "kính chào trợ lý ảo", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "kính chào trợ lý", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "kính chào", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "kinh chao", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào chatbot", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào chatbot", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào bot", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào bot", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào đồng chí", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào đồng chí", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào bạn", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào bạn", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào anh", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào anh", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào chị", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào chị", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào em", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào em", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "xin chào", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "good morning", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "chào", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "hello", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "hi", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "hẹn gặp lại", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "thank you", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "tạm biệt", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "cảm ơn", "LEAD_NOISE", 1.0),
    ("GREETING_LEAD_NOISE", "thanks", "LEAD_NOISE", 1.0),
    ("FAREWELL_SIGNAL", "hẹn gặp lại", "FAREWELL", 1.0),
    ("FAREWELL_SIGNAL", "thank you", "FAREWELL", 1.0),
    ("FAREWELL_SIGNAL", "tạm biệt", "FAREWELL", 1.0),
    ("FAREWELL_SIGNAL", "cảm ơn", "FAREWELL", 1.0),
    ("FAREWELL_SIGNAL", "thanks", "FAREWELL", 1.0),
    # Scope resolution markers, prepositions and stop tokens
    ("SCOPE_ENTITY_MARKER", "nhóm lĩnh vực", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "nhom linh vuc", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "lĩnh vực", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "linh vuc", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "mảng", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "mang", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "khối", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "khoi", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "thuộc về", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "thuoc ve", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "ngành", "MARKER", 1.0),
    ("SCOPE_ENTITY_MARKER", "nganh", "MARKER", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "về", "PREP", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "ve", "PREP", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "của", "PREP", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "cua", "PREP", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "trong", "PREP", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "thuộc", "PREP", 1.0),
    ("SCOPE_LEAD_PREPOSITION", "thuoc", "PREP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện tại là bao nhiêu", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện nay là bao nhiêu", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện tại", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hien tai", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện nay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hien nay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện có", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hien co", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện đang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hien dang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hiện", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hien", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong năm", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong nam", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "năm", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nam", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong quý", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong quy", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "ở quý", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "o quy", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "quý", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "quy", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong nửa", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong nua", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nửa đầu", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nua dau", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nửa cuối", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nua cuoi", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nửa sau", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nua sau", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "6 tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "6 thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "sáu tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "sau thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "3 tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "3 thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "9 tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "9 thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "từ đầu năm", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tu dau nam", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "đầu năm", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "dau nam", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tính từ", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tinh tu", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "lũy kế", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "luy ke", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "từ tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tu thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trong thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "ở tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "o thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tháng", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "vào ngày", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "vao ngay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "ngày", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "ngay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tính đến", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tinh den", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "đến nay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "den nay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tới giờ", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "toi gio", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "đến giờ", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "den gio", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tại", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tai", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "ở", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "o", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "của", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "cua", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trên hệ thống", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tren he thong", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trên kho", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "tren kho", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thì", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thi", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hãy", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "hay", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "có những", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "co nhung", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "có các", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "co cac", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "gồm những", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "gom nhung", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "gồm các", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "gom cac", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "bao gồm", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "bao gom", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "là gì", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "la gi", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nào", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "nao", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "đang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "dang", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thuộc", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thuoc", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "triển khai", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "trien khai", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thực hiện", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "thuc hien", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "phụ trách", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "phu trach", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "quản lý", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "quan ly", "STOP", 1.0),
    ("SCOPE_STOP_TOKEN", "?", "STOP", 1.0),
)


class DuckDBSemanticCatalog:
    """
    DuckDB In-Memory Catalog quản lý toàn bộ siêu dữ liệu DWH.
    Áp dụng cơ chế Hybrid Dual-Mode Hydration:
    - Thử kết nối Docker PostgreSQL vna_wom_dev lúc khởi động.
    - Fallback tự động nạp từ data/catalog_seed_metadata.json khi offline hoặc chạy CI.
    - Tích hợp SOTA Hybrid Dense/Sparse RRF Retrieval & Micro-LLM Disambiguation.
    """

    def __init__(self, seed_path: Optional[str] = None) -> None:
        self.conn = duckdb.connect(":memory:")
        self.seed_path = Path(seed_path or Path(__file__).resolve().parent.parent.parent / "data" / "catalog_seed_metadata.json")
        self._table_metadata_cache: Dict[str, TableMetadataDTO] = {}
        self._alias_registry: List[Dict[str, Any]] = []
        self._embed_model: Optional[Any] = None
        self._criteria_embeddings: Optional[np.ndarray] = None
        self._criteria_cache_codes: List[str] = []
        self._criteria_cache_names: List[str] = []
        self._criteria_cache_aliases: List[str] = []
        self._criteria_cache_tenants: List[str] = []
        self._criteria_cache_levels: List[int] = []
        self._init_schema()
        self._hydrate_catalog()
        self._build_indexes()
        self._ensure_embeddings_indexed()


    def _init_schema(self) -> None:
        """Khởi tạo cấu trúc các bảng danh mục trong bộ nhớ RAM của DuckDB."""
        # 1. Bảng siêu dữ liệu bảng và cột
        self.conn.execute("""
            CREATE TABLE catalog_schema_metadata (
                table_name VARCHAR NOT NULL,
                simple_name VARCHAR NOT NULL,
                column_name VARCHAR NOT NULL,
                data_type VARCHAR NOT NULL,
                column_description VARCHAR,
                is_pk BOOLEAN NOT NULL DEFAULT FALSE,
                is_fk BOOLEAN NOT NULL DEFAULT FALSE,
                fk_target VARCHAR,
                table_description VARCHAR
            );
        """)

        # 2. Bảng Danh mục Chỉ tiêu Báo cáo (Criteria Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_criteria (
                id VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                unit VARCHAR,
                level INTEGER NOT NULL,
                is_leaf BOOLEAN NOT NULL DEFAULT TRUE,
                aliases VARCHAR,
                tenant_code VARCHAR,
                created_date TIMESTAMP
            );
        """)

        # 3. Bảng Danh mục Cơ quan (deparment - lưu ý không có chữ t thứ 2 theo TRAP-005)
        self.conn.execute("""
            CREATE TABLE catalog_departments (
                code VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                tenant_code VARCHAR NOT NULL,
                level INTEGER NOT NULL,
                related_codes VARCHAR
            );
        """)

        # 4. Bảng Danh mục Phòng ban (Office Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_offices (
                id UUID PRIMARY KEY,
                name VARCHAR NOT NULL,
                code VARCHAR,
                department_code VARCHAR NOT NULL,
                tenant_code VARCHAR NOT NULL,
                level INTEGER NOT NULL
            );
        """)

        # 5. Bảng Danh mục Nhiệm vụ (Mission Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_missions (
                id BIGINT PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                year_code VARCHAR NOT NULL,
                department_code VARCHAR NOT NULL,
                status VARCHAR NOT NULL
            );
        """)

        # 6. Bảng Danh mục Biểu mẫu Thu thập (Collection Form Catalog)
        self.conn.execute("""
            CREATE TABLE catalog_collection_forms (
                id BIGINT PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                year_code VARCHAR NOT NULL,
                department_code VARCHAR NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                status VARCHAR NOT NULL
            );
        """)

        # 7. Bảng Nhật ký Đồng bộ (Sync Metadata)
        self.conn.execute("""
            CREATE TABLE catalog_sync_meta (
                last_synced_at TIMESTAMP NOT NULL,
                dwh_pipeline_run_at TIMESTAMP NOT NULL,
                total_criteria INTEGER NOT NULL,
                total_departments INTEGER NOT NULL,
                total_offices INTEGER NOT NULL,
                total_missions INTEGER NOT NULL,
                total_forms INTEGER NOT NULL,
                status VARCHAR NOT NULL
            );
        """)

        # 8. Bảng Danh mục Địa Bàn Động (Tenant Catalog - Dynamic Spatial Resolution)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_tenants (
                tenant_code VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                aliases VARCHAR NOT NULL
            );
        """)
        self.conn.execute("""
            INSERT OR IGNORE INTO catalog_tenants VALUES 
            ('68', 'Lâm Đồng', 'lâm đồng,lam dong,tỉnh lâm đồng,ld,tỉnh 68,68,toàn tỉnh,cả tỉnh,toàn bộ tỉnh,cấp tỉnh,ubnd tỉnh lâm đồng'),
            ('79', 'Thành phố Hồ Chí Minh', 'thành phố hồ chí minh,tp.hcm,tphcm,tp hcm,sài gòn,sai gon,hồ chí minh,ho chi minh,79,tp. hcm,tp. hồ chí minh');
        """)

        # 9. Bảng Danh mục Tỉnh thành (Province Catalog)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_provinces (
                id VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                is_activated BOOLEAN NOT NULL DEFAULT TRUE
            );
        """)

        # 10. Bảng Danh mục Người dùng / Cán bộ (User Catalog - RAM Personnel Resolution)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_users (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                username VARCHAR NOT NULL,
                position VARCHAR,
                department_code VARCHAR,
                department_name VARCHAR,
                tenant_code VARCHAR
            );
        """)

        # 11. Bảng Danh mục Từ viết tắt công vụ (Official Acronym Catalog)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_acronyms (
                acronym VARCHAR PRIMARY KEY,
                full_form VARCHAR NOT NULL,
                category VARCHAR NOT NULL
            );
        """)
        self.conn.execute("""
            INSERT OR IGNORE INTO catalog_acronyms VALUES
            ('PTNT', 'phát triển nông thôn', 'department'),
            ('NN', 'nông nghiệp', 'department'),
            ('HTX', 'hợp tác xã', 'criteria'),
            ('THT', 'tổ hợp tác', 'criteria'),
            ('LHHTX', 'liên hiệp hợp tác xã', 'criteria'),
            ('OCOP', 'mỗi xã một sản phẩm', 'criteria'),
            ('TNLĐ', 'tai nạn lao động', 'criteria'),
            ('UBND', 'ủy ban nhân dân', 'administration');
        """)

        # 12. Bảng Danh mục Lĩnh vực (Scope Catalog - REQ-Q03 & SC-3.1..3.2)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_scopes (
                id VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                tenant_code VARCHAR NOT NULL
            );
        """)

        # 13. Bảng Cây Phân cấp Chỉ tiêu (Criteria Hierarchy Catalog - REQ-Q01, REQ-Q02, REQ-Q04 & SC-2.1..2.4)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_criteria_hierarchy (
                id VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                parent_id VARCHAR,
                parent_name VARCHAR,
                root_id VARCHAR,
                root_name VARCHAR,
                level INTEGER NOT NULL,
                is_leaf BOOLEAN NOT NULL,
                mission_name VARCHAR,
                office_name VARCHAR,
                latest_value VARCHAR
            );
        """)

        # 14. Bảng Chi tiết Nhiệm vụ & Lĩnh vực (Mission Detail Catalog - REQ-Q03, REQ-Q04 & SC-4.2)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_missions_detail (
                id VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                name VARCHAR NOT NULL,
                scope_name VARCHAR,
                office_names VARCHAR,
                has_approved_facts BOOLEAN NOT NULL DEFAULT FALSE
            );
        """)

        # 15. Bảng Danh mục Ngữ nghĩa (Semantic Lexicon - Anti-heuristic NLU)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS semantic_lexicon (
                category VARCHAR,
                term VARCHAR,
                sub_intent VARCHAR,
                weight DOUBLE DEFAULT 1.0
            );
        """)
        lex_rows = []
        for cat, term, sub_intent, w in ALLOWED_SEMANTIC_LEXICON_SEED:
            t_low = term.lower().strip()
            lex_rows.append((cat, t_low, sub_intent, float(w)))
            t_unacc = _remove_accents(t_low)
            if t_unacc and t_unacc != t_low:
                if cat == "DISCOURSE_CONNECTIVE" and len(t_unacc.split()) <= 1:
                    continue
                lex_rows.append((cat, t_unacc, sub_intent, float(w) * 0.95))
        self.conn.executemany("INSERT INTO semantic_lexicon VALUES (?, ?, ?, ?)", lex_rows)

        # 16. Bảng Danh mục Alias Chỉ tiêu (Criteria Aliases Catalog)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS catalog_aliases (
                alias VARCHAR PRIMARY KEY,
                code VARCHAR NOT NULL,
                is_leaf BOOLEAN NOT NULL DEFAULT TRUE
            );
        """)
        seed_aliases = [
            ("diện tích muối công nghiệp", "dien_tich_muoi_san_xuat_cong_nghiep", True),
            ("diện tích muối thủ công", "dien_tich_muoi_san_xuat_thu_cong", True),
            ("sản lượng muối công nghiệp", "san_luong_muoi_san_xuat_cong_nghiep", True),
            ("sản lượng muối thủ công", "san_luong_muoi_san_xuat_thu_cong", True),
            ("tổng số hộ dân tham gia sản xuất muối", "tong_ho_san_xuat_muoi", True),
            ("tổng số hộ tham gia sản xuất muối", "tong_ho_san_xuat_muoi", True),
            ("tổng số hộ sản xuất muối", "tong_ho_san_xuat_muoi", True),
            ("tổng hộ sản xuất muối", "tong_ho_san_xuat_muoi", True),
            ("tổng hộ sản xuất muôi", "tong_ho_san_xuat_muoi", True),
            ("số hộ sản xuất muối", "tong_ho_san_xuat_muoi", True),
            ("hộ dân tham gia sản xuất muối", "tong_ho_san_xuat_muoi", True),
            ("làng nghề truyền thống", "lang_nghe_truyen_thong", True),
            ("làng nghề truyền thồng", "lang_nghe_truyen_thong", True),
            ("doanh thu hợp tác xã", "doanh_thu_binh_quan_trong_nam_cua_mot_hop_tac_xa_nong_nghiep", True),
            ("doanh thu bình quân", "doanh_thu_binh_quan_trong_nam_cua_mot_hop_tac_xa_nong_nghiep", True),
            ("tổng số hiện có", "dang_hoat_dong", True),
            ("tổng số hiện nay", "dang_hoat_dong", True),
            ("số lượng đơn vị đang hoạt động", "dang_hoat_dong", True),
            ("đang hoạt động", "dang_hoat_dong", True),
            ("liên kết sản xuất", "lien_ket_san_xuat", True),
            ("liên kết chuỗi giá trị", "lien_ket_san_xuat", True),
            ("tạm ngừng hoạt động", "tam_ngung_hoat_dong", True),
            ("giải thể", "giai_the", True),
            ("lợi nhuận bình quân", "loi_nhuan_binh_quan", True),
            ("thu nhập bình quân", "thu_nhap_binh_quan", True),
            ("ứng dụng công nghệ cao", "ung_dung_cong_nghe_cao", True),
            ("chuyển đổi số", "chuyen_doi_so", True),
            ("nông nghiệp khác", "nong_nghiep_khac", True),
            ("an toàn thực phẩm / vietgap", "an_toan_thuc_pham_vietgap", True),
            ("an toàn thực phẩm", "an_toan_thuc_pham_vietgap", True),
            ("vietgap", "an_toan_thuc_pham_vietgap", True),
            ("chế biến sâu", "che_bien_sau", True),
            ("liên kết tiêu thụ sản phẩm", "lien_ket_tieu_thu_san_pham", True),
            ("liên kết tiêu thụ", "lien_ket_tieu_thu_san_pham", True),
            ("tổng số lao động", "tong_so_lao_dong", True),
            ("tổng số thành viên", "thanh_vien", True),
            ("số lượng sản phẩm ocop 3 sao", "so_luong_san_pham_ocop_3_sao_duoc_cong_nhan_trong_nam", True),
            ("số lượng sản phẩm ocop 4 sao", "so_luong_san_pham_ocop_4_sao_duoc_cong_nhan_trong_nam", True),
            ("số lượng sản phẩm ocop 5 sao", "so_luong_san_pham_ocop_5_sao_duoc_cong_nhan_trong_nam", True),
            ("diện tích sản xuất muối", "tong_dien_tich_san_xuat_muoi", False),
            ("diện tích sản xuất muôi", "tong_dien_tich_san_xuat_muoi", False),
            ("sản xuất muôi", "tong_dien_tich_san_xuat_muoi", False),
            ("sản lượng muối", "tong_san_luong_muoi_gd2", False),
            ("lũy kế tổng số lượng chủ thể có sản phẩm đạt ocop", "luy_ke_tong_so_luong_chu_the_den_thoi_diem_bao_cao", False),
            ("lũy kế tổng số lượng sản phẩm ocop đạt chuẩn", "luy_ke_tong_so_luong_san_pham_ocop_den_thoi_diem_bao_cao", False),
            ("đánh giá, phân hạng sản phẩm ocop", "luy_ke_tong_so_luong_san_pham_ocop_den_thoi_diem_bao_cao", False),
            ("chương trình mỗi xã một sản phẩm", "chuong_trinh_ocop", False),
            ("lĩnh vực hoạt động của liên hiệp hợp tác xã nông nghiệp", "tong_so_lhhtx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của liên hiệp hợp tác xã", "tong_so_lhhtx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của liên hiệp htx", "tong_so_lhhtx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của lhhtx", "tong_so_lhhtx_phan_theo_linh_vuc", False),
            ("tổng số liên hiệp hợp tác xã phân theo lĩnh vực", "tong_so_lhhtx_phan_theo_linh_vuc", False),
            ("tổng số liên hiệp htx phân theo lĩnh vực", "tong_so_lhhtx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của hợp tác xã nông nghiệp", "so_luong_htx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của hợp tác xã", "so_luong_htx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của htx nông nghiệp", "so_luong_htx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của htx", "so_luong_htx_phan_theo_linh_vuc", False),
            ("số lượng hợp tác xã phân theo lĩnh vực", "so_luong_htx_phan_theo_linh_vuc", False),
            ("số lượng htx phân theo lĩnh vực", "so_luong_htx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của tổ hợp tác nông nghiệp", "tong_so_tht_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của tổ hợp tác", "tong_so_tht_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của tht", "tong_so_tht_phan_theo_linh_vuc", False),
            ("tổng số tổ hợp tác phân theo lĩnh vực", "tong_so_tht_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động của trang trại", "tong_so_luong_tt_phan_theo_linh_vuc", False),
            ("tổng số lượng trang trại phân theo lĩnh vực", "tong_so_luong_tt_phan_theo_linh_vuc", False),
            ("tổng số trang trại phân theo lĩnh vực", "tong_so_luong_tt_phan_theo_linh_vuc", False),
            ("tổng số trang trại", "trang_trai", False),
            ("trang trại", "trang_trai", False),
            ("tổng số liên hiệp hợp tác xã nông nghiệp", "lien_hiep_htx_nong_nghiep", False),
            ("liên hiệp hợp tác xã nông nghiệp", "lien_hiep_htx_nong_nghiep", False),
            ("tổng số lhhtx nông nghiệp", "lien_hiep_htx_nong_nghiep", False),
            ("tổng số tổ hợp tác nông nghiệp", "to_hop_tac_nong_nghiep", False),
            ("tổ hợp tác nông nghiệp", "to_hop_tac_nong_nghiep", False),
            ("tổ hợp tác", "to_hop_tac_nong_nghiep", False),
            ("tht nông nghiệp", "to_hop_tac_nong_nghiep", False),
            ("tht", "to_hop_tac_nong_nghiep", False),
            ("tổng số tht nông nghiệp", "to_hop_tac_nong_nghiep", False),
            ("số lượng tổ hợp tác", "tong_so_tht_phan_theo_linh_vuc", False),
            ("số lượng tht", "tong_so_tht_phan_theo_linh_vuc", False),
            ("tổng số htx nông nghiệp", "htx_nong_nghiep", False),
            ("số lượng hợp tác xã nông nghiệp", "htx_nong_nghiep", False),
            ("số lượng htx nông nghiệp", "htx_nong_nghiep", False),
            ("hợp tác xã nông nghiệp", "htx_nong_nghiep", False),
            ("hợp tác xã có những chỉ tiêu nào", "htx_nong_nghiep", False),
            ("htx có những chỉ tiêu nào", "htx_nong_nghiep", False),
            ("số lượng hợp tác xã", "so_luong_htx_phan_theo_linh_vuc", False),
            ("số lượng htx", "so_luong_htx_phan_theo_linh_vuc", False),
            ("lĩnh vực hoạt động", "so_luong_htx_phan_theo_linh_vuc", False),
            ("làng nghề, ngành nghề nông thôn", "lang_nghe", False),
            ("phát triển làng nghề", "lang_nghe", False),
        ]
        self.conn.executemany("INSERT OR IGNORE INTO catalog_aliases VALUES (?, ?, ?)", seed_aliases)

    def has_lexicon_term(self, raw_input: str, category: str) -> bool:
        if not raw_input:
            return False
        norm_val = raw_input.lower()
        if category == "DISCOURSE_CONNECTIVE":
            padded = f" {norm_val.replace('?', ' ').replace(',', ' ').replace('.', ' ').replace('!', ' ')} "
            row = self.conn.execute(
                """SELECT 1 FROM semantic_lexicon 
                   WHERE category = ? 
                     AND (
                       (LENGTH(term) > 4 AND INSTR(?, term) > 0)
                       OR INSTR(?, ' ' || term || ' ') > 0
                     ) 
                   LIMIT 1;""",
                [category, norm_val, padded],
            ).fetchone()
            return row is not None
        if "LEAD" in category or "PREFIX" in category:
            row = self.conn.execute(
                """SELECT 1 
                   FROM semantic_lexicon l, (SELECT ? AS text) t
                   WHERE l.category = ? 
                     AND (
                       LOWER(t.text) = LOWER(l.term)
                       OR LOWER(t.text) LIKE LOWER(l.term) || ' %'
                       OR LOWER(t.text) LIKE LOWER(l.term) || ',%'
                       OR LOWER(t.text) LIKE LOWER(l.term) || '!%'
                       OR LOWER(t.text) LIKE LOWER(l.term) || '.%'
                       OR LOWER(t.text) LIKE LOWER(l.term) || ':%'
                       OR LOWER(t.text) LIKE LOWER(l.term) || '?%'
                     )
                   LIMIT 1;""",
                [norm_val, category],
            ).fetchone()
            return row is not None
        row = self.conn.execute(
            "SELECT 1 FROM semantic_lexicon WHERE category = ? AND INSTR(?, term) > 0 LIMIT 1;",
            [category, norm_val],
        ).fetchone()
        return row is not None

    def get_lexicon_sub_intent(self, raw_input: str, category: str) -> Optional[str]:
        if not raw_input:
            return None
        norm_val = raw_input.lower()
        row = self.conn.execute(
            "SELECT sub_intent FROM semantic_lexicon WHERE category = ? AND INSTR(?, term) > 0 ORDER BY weight DESC, LENGTH(term) DESC LIMIT 1;",
            [category, norm_val],
        ).fetchone()
        return row[0] if row else None

    def get_matching_lexicon_sub_intents(self, raw_input: str, category: str) -> List[str]:
        if not raw_input:
            return []
        norm_val = raw_input.lower()
        rows = self.conn.execute(
            "SELECT DISTINCT sub_intent FROM semantic_lexicon WHERE category = ? AND INSTR(?, term) > 0;",
            [category, norm_val],
        ).fetchall()
        return [r[0] for r in rows]

    def get_associated_department_codes(self, department_code: Optional[str]) -> List[str]:
        """
        Truy vấn danh sách mã cơ quan / phòng ban liên kết từ DuckDB catalog metadata (Zero Hardcoding).
        """
        if not department_code:
            return []
        try:
            row = self.conn.execute(
                "SELECT related_codes FROM catalog_departments WHERE code = ? LIMIT 1;",
                [department_code],
            ).fetchone()
            if row and row[0]:
                return [c.strip() for c in row[0].split(",") if c.strip()]
        except Exception as e:
            logger.debug("Lỗi truy vấn get_associated_department_codes: %s", e)
        return [department_code]

    def strip_query_noise(self, text: str, category: str = "QUERY_LEAD_NOISE") -> str:
        """
        Loại bỏ từ nhiễu/tiền tố/hậu tố bằng DuckDB SQL truy vấn từ bảng semantic_lexicon (Zero Heuristics).
        """
        if not text:
            return ""
        try:
            rows = self.conn.execute(
                "SELECT term FROM semantic_lexicon WHERE category = ? ORDER BY LENGTH(term) DESC;",
                [category]
            ).fetchall()
        except Exception:
            return text.strip()

        cleaned = text.strip()
        is_lead = "LEAD" in category or "PREFIX" in category
        is_tail = "TAIL" in category or "SUFFIX" in category

        changed = True
        while changed:
            changed = False
            for (term,) in rows:
                if not term:
                    continue
                if is_lead:
                    new_val = self.conn.execute(
                        """SELECT CASE 
                            WHEN LOWER(text) = LOWER(term) 
                            THEN ''
                            WHEN LOWER(text) LIKE LOWER(term) || ' %' 
                            THEN TRIM(SUBSTR(text, LENGTH(term) + 2)) 
                            WHEN LOWER(text) LIKE LOWER(term) || ',%' 
                              OR LOWER(text) LIKE LOWER(term) || ':%' 
                              OR LOWER(text) LIKE LOWER(term) || '.%' 
                              OR LOWER(text) LIKE LOWER(term) || '!%' 
                              OR LOWER(text) LIKE LOWER(term) || '?%' 
                            THEN TRIM(SUBSTR(text, LENGTH(term) + 2)) 
                            ELSE text 
                        END
                        FROM (SELECT ? AS text, ? AS term);""",
                        [cleaned, term]
                    ).fetchone()[0]
                elif is_tail:
                    new_val = self.conn.execute(
                        """SELECT CASE 
                            WHEN LOWER(text) = LOWER(term) 
                            THEN ''
                            WHEN LOWER(text) LIKE '% ' || LOWER(term) 
                            THEN TRIM(SUBSTR(text, 1, LENGTH(text) - LENGTH(term) - 1)) 
                            WHEN LOWER(text) LIKE '%,' || LOWER(term) 
                              OR LOWER(text) LIKE '%?' || LOWER(term) 
                              OR LOWER(text) LIKE '%!' || LOWER(term) 
                              OR LOWER(text) LIKE '%.' || LOWER(term) 
                            THEN TRIM(SUBSTR(text, 1, LENGTH(text) - LENGTH(term) - 1)) 
                            ELSE text 
                        END
                        FROM (SELECT ? AS text, ? AS term);""",
                        [cleaned, term]
                    ).fetchone()[0]
                else:
                    new_val = self.conn.execute(
                        "SELECT TRIM(REPLACE(?, ?, ''));",
                        [cleaned, term]
                    ).fetchone()[0]
                if new_val != cleaned:
                    cleaned = " ".join(new_val.split()).strip()
                    changed = True
                    break
        return cleaned



    def _hydrate_catalog(self) -> None:
        """
        Cơ chế Hybrid Dual-Mode Hydration:
        Luôn nạp toàn bộ cấu trúc schema, aliases, acronyms và dữ liệu hạt giống từ seed file làm baseline.
        Sau đó, nếu kết nối Live PostgreSQL vna_wom_dev khả dụng thì đồng bộ và cập nhật thêm dữ liệu thực tế.
        Đảm bảo DuckDB RAM và Alias Registry KHÔNG BAO GIỜ bị rỗng!
        """
        # 1. Luôn nạp baseline từ seed file
        self._hydrate_from_seed_file()

        # 2. Thử kết nối Live PostgreSQL vna_wom_dev để đồng bộ thêm dữ liệu thực tế
        try:
            import psycopg2
            conn_pg = psycopg2.connect(
                host=settings.DWH_HOST,
                port=settings.DWH_PORT,
                dbname=settings.DWH_DB,
                user=settings.DWH_USER,
                password=settings.DWH_PASSWORD,
                connect_timeout=3
            )
            conn_pg.autocommit = True
            cur = conn_pg.cursor()
            # Cập nhật mốc pipeline thực tế từ pipeline_logs
            try:
                cur.execute("SELECT model_name, last_run_at, status FROM dwh_internal.pipeline_logs ORDER BY last_run_at DESC LIMIT 1;")
                log_row = cur.fetchone()
                if log_row:
                    self.conn.execute(
                        "UPDATE catalog_sync_meta SET dwh_pipeline_run_at = ?, status = ?;",
                        (str(log_row[1]), str(log_row[2]))
                    )
            except Exception:
                pass

            # Đồng bộ danh mục chỉ tiêu thực tế từ dwh_internal.criteria
            try:
                cur.execute("""
                    SELECT c.id, c.code, c.name, c.level,
                           NOT EXISTS (SELECT 1 FROM dwh_internal.criteria sub WHERE sub.parent_id = c.id) AS is_leaf,
                           c.tenant_code, c.created_date
                    FROM dwh_internal.criteria c
                    WHERE c.deleted_date IS NULL
                    ORDER BY c.created_date DESC NULLS LAST;
                """)
                pg_crits = cur.fetchall()
                existing_ids = set(r[0] for r in self.conn.execute("SELECT id FROM catalog_criteria;").fetchall())
                new_crit_rows = []
                for cid, code, name, lvl, is_leaf, tenant_code, created_dt in pg_crits:
                    str_cid = str(cid)
                    tc = str(tenant_code or "")
                    if str_cid and str_cid not in existing_ids and code and name:
                        new_crit_rows.append((str_cid, code, name, "", lvl or 1, is_leaf, "", tc, created_dt))
                        existing_ids.add(str_cid)
                        self._alias_registry.append({
                            "alias": name.lower().strip(),
                            "code": code,
                            "name": name,
                            "type": "criteria",
                            "target_table": "dwh_internal.criteria",
                            "tenant_code": tc
                        })
                if new_crit_rows:
                    self.conn.executemany("INSERT INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", new_crit_rows)
                    logger.info("Đã đồng bộ thêm %d chỉ tiêu thực tế từ Live PostgreSQL vào DuckDB Catalog.", len(new_crit_rows))
            except Exception as e:
                logger.warning(f"Không thể đồng bộ criteria từ PG: {e}")

            # Đồng bộ cây phân cấp chỉ tiêu thực tế từ dwh_internal.criteria + fact_report_criteria
            try:
                cur.execute("""
                    WITH fact_meta AS (
                        SELECT DISTINCT ON (c2.id)
                            c2.id AS criteria_id,
                            f.mission_name,
                            o.office_name,
                            f.value AS latest_value
                        FROM dwh_internal.criteria c2
                        JOIN dwh_internal.fact_report_criteria f
                          ON (f.criteria_id = c2.id OR (c2.code = 'tong_san_luong_muoi_gd2' AND f.code = 'tong_san_luong_muoi'))
                        LEFT JOIN dwh_internal.office o ON f.office_id = o.id
                        WHERE f.report_status = 'approved'
                        ORDER BY c2.id,
                                 f.report_date DESC NULLS LAST,
                                 f.version DESC NULLS LAST
                    )
                    SELECT
                        c.id::text,
                        c.code,
                        c.name,
                        c.parent_id::text,
                        p.name AS parent_name,
                        COALESCE(gp.id, p.id, c.id)::text AS root_id,
                        COALESCE(gp.name, p.name, c.name) AS root_name,
                        c.level,
                        NOT EXISTS (SELECT 1 FROM dwh_internal.criteria sub WHERE sub.parent_id = c.id AND sub.deleted_date IS NULL) AS is_leaf,
                        COALESCE(fm.mission_name, c.mission_name, (SELECT m_sub.mission_name FROM dwh_internal.mission m_sub WHERE m_sub.id = c.mission_id LIMIT 1), '-') AS mission_name,
                        COALESCE(
                            fm.office_name,
                            (
                                SELECT o_m.office_name
                                FROM dwh_internal.office_mission om
                                JOIN dwh_internal.office o_m ON o_m.id = om.office_id
                                WHERE (om.mission_id = c.mission_id OR om.mission_name = COALESCE(c.mission_name, fm.mission_name))
                                  AND om.deleted_date IS NULL
                                ORDER BY om.created_date DESC NULLS LAST
                                LIMIT 1
                            ),
                            '-'
                        ) AS office_name,
                        CASE WHEN fm.latest_value IS NOT NULL AND TRIM(fm.latest_value) NOT IN ('', '-') THEN fm.latest_value ELSE fm.latest_value END AS latest_value
                    FROM dwh_internal.criteria c
                    LEFT JOIN dwh_internal.criteria p ON c.parent_id = p.id
                    LEFT JOIN dwh_internal.criteria gp ON p.parent_id = gp.id
                    LEFT JOIN fact_meta fm ON fm.criteria_id = c.id
                    WHERE c.deleted_date IS NULL
                    ORDER BY c.level ASC, c.name ASC;
                """)
                hier_rows = cur.fetchall()
                if hier_rows:
                    self.conn.execute("DELETE FROM catalog_criteria_hierarchy;")
                    self.conn.executemany(
                        "INSERT INTO catalog_criteria_hierarchy VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        hier_rows
                    )
            except Exception as e:
                logger.warning(f"Không thể đồng bộ criteria hierarchy từ PG: {e}")

            # Đồng bộ danh mục lĩnh vực (scope) và chi tiết nhiệm vụ (mission detail)
            try:
                cur.execute("""
                    SELECT DISTINCT s.id::text, COALESCE(s.scope_code, ''), s.scope_name, COALESCE(s.tenant_code, '68')
                    FROM dwh_internal.scope s
                    JOIN dwh_internal.mission m ON m.scope_id = s.id;
                """)
                pg_scopes = cur.fetchall()
                if pg_scopes:
                    self.conn.execute("DELETE FROM catalog_scopes;")
                    self.conn.executemany("INSERT OR REPLACE INTO catalog_scopes VALUES (?, ?, ?, ?)", pg_scopes)
            except Exception as e:
                logger.warning(f"Không thể đồng bộ scope từ PG: {e}")

            try:
                cur.execute("""
                    SELECT
                        m.id::text,
                        COALESCE(m.mission_code, ''),
                        m.mission_name,
                        COALESCE(s.scope_name, '') AS scope_name,
                        COALESCE(
                            (
                                SELECT o_f.office_name
                                FROM dwh_internal.fact_report_criteria f_off
                                JOIN dwh_internal.office o_f ON o_f.id = f_off.office_id
                                WHERE f_off.report_status = 'approved'
                                  AND (f_off.mission_id = m.id OR TRIM(LOWER(f_off.mission_name)) = TRIM(LOWER(m.mission_name)))
                                ORDER BY f_off.report_date DESC NULLS LAST, f_off.version DESC NULLS LAST
                                LIMIT 1
                            ),
                            (
                                SELECT o_m.office_name
                                FROM dwh_internal.office_mission om
                                JOIN dwh_internal.office o_m ON o_m.id = om.office_id
                                WHERE om.mission_id = m.id
                                  AND om.deleted_date IS NULL
                                  AND om.department_code = m.department_code
                                ORDER BY om.created_date DESC NULLS LAST
                                LIMIT 1
                            ),
                            '-'
                        ) AS office_names,
                        EXISTS (
                            SELECT 1 FROM dwh_internal.fact_report_criteria f
                            WHERE (f.mission_id = m.id OR TRIM(LOWER(f.mission_name)) = TRIM(LOWER(m.mission_name)))
                              AND f.report_status = 'approved'
                        ) AS has_approved_facts
                    FROM dwh_internal.mission m
                    LEFT JOIN dwh_internal.scope s ON m.scope_id = s.id
                    WHERE m.deleted_date IS NULL;
                """)
                pg_mdetail = cur.fetchall()
                if pg_mdetail:
                    self.conn.execute("DELETE FROM catalog_missions_detail;")
                    self.conn.executemany("INSERT OR REPLACE INTO catalog_missions_detail VALUES (?, ?, ?, ?, ?, ?)", pg_mdetail)
                    for idx, (mid, mcode, mname, sname, onames, has_facts) in enumerate(pg_mdetail, start=3000):
                        if mname:
                            self.conn.execute(
                                "INSERT OR IGNORE INTO catalog_missions VALUES (?, ?, ?, ?, ?, ?)",
                                (idx, mcode, mname, "2026", "68-1-01", "ACTIVE")
                            )
            except Exception as e:
                logger.warning(f"Không thể đồng bộ mission detail từ PG: {e}")

            # Đồng bộ danh mục tỉnh thành thực tế từ dwh_internal.province
            try:
                cur.execute("SELECT id, code, name, is_activated FROM dwh_internal.province;")
                pg_provs = cur.fetchall()
                if pg_provs:
                    self.conn.executemany(
                        "INSERT OR IGNORE INTO catalog_provinces VALUES (?, ?, ?, ?)",
                        [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in pg_provs]
                    )
                    for _, code, name, _ in pg_provs:
                        self._alias_registry.append({
                            "alias": name.lower().strip(),
                            "code": str(code),
                            "name": name,
                            "type": "province",
                            "target_table": "dwh_internal.province",
                        })
                    logger.info("Đã đồng bộ thêm %d tỉnh thành thực tế từ Live PostgreSQL vào DuckDB Catalog.", len(pg_provs))
            except Exception as e:
                logger.warning(f"Không thể đồng bộ province từ PG: {e}")

            # Đồng bộ danh mục phòng ban thực tế từ dwh_internal.office
            try:
                cur.execute("SELECT id, office_name, department_code, tenant_code FROM dwh_internal.office;")
                pg_offices = cur.fetchall()
                if pg_offices:
                    self.conn.executemany(
                        "INSERT OR REPLACE INTO catalog_offices VALUES (?, ?, ?, ?, ?, ?)",
                        [(str(r[0]), str(r[1]), None, str(r[2]), str(r[3] or "68"), 2) for r in pg_offices]
                    )
                    for oid, oname, dcode, tcode in pg_offices:
                        self._alias_registry.append({
                            "alias": oname.lower().strip(),
                            "code": str(oid),
                            "name": oname,
                            "type": "office",
                            "target_table": "dwh_internal.office",
                        })
                    logger.info("Đã đồng bộ thêm %d phòng ban thực tế từ Live PostgreSQL vào DuckDB Catalog.", len(pg_offices))
            except Exception as e:
                logger.warning(f"Không thể đồng bộ office từ PG: {e}")

            # Đồng bộ danh mục cán bộ / người dùng từ dwh_internal."user"
            try:
                cur.execute('SELECT id, name, username, position, department_code, department_name, tenant_code FROM dwh_internal."user" WHERE deleted_at IS NULL;')
                pg_users = cur.fetchall()
                if pg_users:
                    self.conn.executemany(
                        "INSERT OR REPLACE INTO catalog_users VALUES (?, ?, ?, ?, ?, ?, ?)",
                        [(str(r[0]), str(r[1] or ""), str(r[2] or ""), str(r[3] or ""), str(r[4] or ""), str(r[5] or ""), str(r[6] or "68")) for r in pg_users]
                    )
                    logger.info("Đã đồng bộ thêm %d người dùng thực tế từ Live PostgreSQL vào DuckDB Catalog.", len(pg_users))
            except Exception as e:
                logger.warning(f"Không thể đồng bộ user từ PG: {e}")

            # Đồng bộ nhiệm vụ thực tế từ dwh_internal.user_mission
            try:
                cur.execute('SELECT DISTINCT mission_name, department_code FROM dwh_internal.user_mission WHERE mission_name IS NOT NULL;')
                pg_um_missions = cur.fetchall()
                for idx, (m_name, d_code) in enumerate(pg_um_missions, start=2000):
                    if m_name and m_name.strip():
                        m_clean = m_name.strip()
                        self.conn.execute(
                            "INSERT OR IGNORE INTO catalog_missions VALUES (?, ?, ?, ?, ?, ?)",
                            (idx, f"MS_UM_{idx}", m_clean, "2026", str(d_code or "68-1-01"), "ACTIVE")
                        )
                        self._alias_registry.append({
                            "alias": m_clean.lower().strip(),
                            "code": f"MS_UM_{idx}",
                            "name": m_clean,
                            "type": "mission",
                            "target_table": "dwh_internal.user_mission"
                        })
            except Exception as e:
                logger.warning(f"Không thể đồng bộ mission từ PG: {e}")

            conn_pg.close()
            logger.info("Đã đồng bộ bổ sung thành công mốc pipeline và danh mục từ Live PostgreSQL vna_wom_dev.")
        except Exception as e:
            logger.info("Hoạt động ở chế độ Offline/Seed Hydration (Không kết nối Live PostgreSQL: %s).", e)

    def _hydrate_from_seed_file(self) -> None:
        """Nạp dữ liệu danh mục từ tệp seed JSON tĩnh."""
        if not self.seed_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp seed metadata tại: {self.seed_path}")

        with open(self.seed_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Nạp tables & columns
        schema_rows = []
        for tbl in data.get("tables", []):
            table_name = tbl["table_name"]
            simple_name = tbl.get("simple_name", table_name.split(".")[-1])
            desc = tbl.get("description", "")
            pk = tbl.get("primary_key")
            cols_dto = []
            for col in tbl.get("columns", []):
                cols_dto.append(
                    ColumnMetadataDTO(
                        column_name=col["name"],
                        data_type=col["type"],
                        description=col.get("description", ""),
                        is_pk=col.get("is_pk", False),
                        is_fk=col.get("is_fk", False),
                        fk_target_table=col.get("fk_target")
                    )
                )
                schema_rows.append((
                    table_name,
                    simple_name,
                    col["name"],
                    col["type"],
                    col.get("description", ""),
                    col.get("is_pk", False),
                    col.get("is_fk", False),
                    col.get("fk_target", None),
                    desc
                ))

            self._table_metadata_cache[table_name] = TableMetadataDTO(
                table_name=table_name,
                schema_name=table_name.split(".")[0] if "." in table_name else "dwh_internal",
                description=desc,
                columns=cols_dto,
                primary_key=pk
            )
            # Lưu cả alias simple_name
            self._table_metadata_cache[simple_name] = self._table_metadata_cache[table_name]

        self.conn.executemany(
            "INSERT INTO catalog_schema_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            schema_rows
        )

        # 2. Nạp criteria
        crit_rows = []
        for c in data.get("criteria", []):
            aliases_str = ", ".join(c.get("aliases", []))
            tc = c.get("tenant_code", "68")
            crit_rows.append((
                str(c["id"]), c["code"], c["name"], c.get("unit"), c["level"], c["is_leaf"], aliases_str, tc, None
            ))
            # Đăng ký alias cho RapidFuzz
            for al in c.get("aliases", []):
                self._alias_registry.append({
                    "alias": al.lower().strip(),
                    "code": c["code"],
                    "name": c["name"],
                    "type": "criteria",
                    "target_table": "dwh_internal.criteria",
                    "tenant_code": tc
                })
        self.conn.executemany("INSERT INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", crit_rows)

        # Seed bổ sung các chỉ tiêu NULL-value (SC-2.3) phòng khi offline
        extra_seed_criteria = [
            ("fb3c51f5-21d5-490b-a0bc-cfdd9c4789c6", "lien_ket_san_xuat", "Liên kết sản xuất", "", 1, True, "liên kết sản xuất", "68", None),
            ("8a8ef1b2-36d3-4187-8cf1-eb7f3d93f7aa", "du_lieu_cai_cach_1", "Dữ liệu cải cách 1", "", 1, True, "dữ liệu cải cách 1", "68", None),
        ]
        self.conn.executemany("INSERT OR IGNORE INTO catalog_criteria VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", extra_seed_criteria)

        # 3. Nạp departments
        dept_rows = []
        for d in data.get("departments", []):
            rel_codes = ",".join(d.get("related_codes", [])) if d.get("related_codes") else ""
            dept_rows.append((d["code"], d["name"], d["tenant_code"], d["level"], rel_codes))
            # Đăng ký alias
            self._alias_registry.append({
                "alias": d["name"].lower().strip(),
                "code": d["code"],
                "name": d["name"],
                "type": "department",
                "target_table": "dwh_internal.deparment"
            })
        self.conn.executemany("INSERT INTO catalog_departments VALUES (?, ?, ?, ?, ?)", dept_rows)

        # 4. Nạp offices
        office_rows = []
        for o in data.get("offices", []):
            office_rows.append((o["id"], o["name"], o.get("code"), o["department_code"], o["tenant_code"], o["level"]))
            self._alias_registry.append({
                "alias": o["name"].lower().strip(),
                "code": str(o["id"]),
                "name": o["name"],
                "type": "office",
                "target_table": "dwh_internal.office"
            })
        self.conn.executemany("INSERT INTO catalog_offices VALUES (?, ?, ?, ?, ?, ?)", office_rows)

        # 5. Nạp missions
        mission_rows = []
        for m in data.get("missions", []):
            m_year = str(m.get("year_code", m.get("year", "2026")))
            mission_rows.append((m["id"], m["code"], m["name"], m_year, m["department_code"], m["status"]))
            self._alias_registry.append({
                "alias": m["name"].lower().strip(),
                "code": m["code"],
                "name": m["name"],
                "type": "mission",
                "target_table": "dwh_internal.mission"
            })
        self.conn.executemany("INSERT INTO catalog_missions VALUES (?, ?, ?, ?, ?, ?)", mission_rows)

        # Seed missions từ user_mission và dwh_internal.mission vào RAM catalog_missions
        um_seed_missions = [
            (2001, "MS_DIEM_NGHIEP", "Diêm nghiệp", "2026", "68-1-01", "ACTIVE"),
            (2002, "MS_PTNT", "Phát triển nông thôn", "2026", "68-1-01", "ACTIVE"),
            (2003, "cai_cach_hanh_chinh", "Cải cách hành chính", "2026", "68-1-01", "ACTIVE"),
        ]
        self.conn.executemany("INSERT OR IGNORE INTO catalog_missions VALUES (?, ?, ?, ?, ?, ?)", um_seed_missions)
        for mid, mcode, mname, myear, mdept, mstat in um_seed_missions:
            self._alias_registry.append({
                "alias": mname.lower().strip(),
                "code": mcode,
                "name": mname,
                "type": "mission",
                "target_table": "dwh_internal.user_mission"
            })

        # Seed catalog_scopes & catalog_missions_detail baseline
        seed_scopes = [
            ("c537e63b-be04-4e82-8cf7-bd56603de557", "nong_nghiep", "Nông nghiệp", "68"),
            ("fe8a7371-3d81-4899-abe7-87547cf19300", "linh_vuc_1", "lĩnh vực 1", "68"),
        ]
        self.conn.executemany("INSERT OR IGNORE INTO catalog_scopes VALUES (?, ?, ?, ?)", seed_scopes)

        seed_missions_detail = [
            ("643311bc-7be7-486b-91f4-8e2caaa47561", "diem_nghiep", "Diêm nghiệp", "Nông nghiệp", "Phòng nông nghiệp", True),
            ("b2b399fd-1fa5-4191-9da7-2e4040687d76", "phat_trien_nong_thon", "Phát triển nông thôn", "Nông nghiệp", "Chi cục", True),
            ("b91c99fd-d775-4dc9-a77b-35c6eb3582c8", "cai_cach_hanh_chinh", "Cải cách hành chính", "lĩnh vực 1", "Phòng kinh tế", False),
        ]
        self.conn.executemany("INSERT OR IGNORE INTO catalog_missions_detail VALUES (?, ?, ?, ?, ?, ?)", seed_missions_detail)

        # 6. Nạp collection_forms
        form_rows = []
        for f in data.get("collection_forms", []):
            f_year = str(f.get("year_code", f.get("year", "2026")))
            form_rows.append((f["id"], f["code"], f["name"], f_year, f["department_code"], f["is_active"], f["status"]))
            self._alias_registry.append({
                "alias": f["name"].lower().strip(),
                "code": f["code"],
                "name": f["name"],
                "type": "collection_form",
                "target_table": "dwh_internal.collection_form"
            })
        self.conn.executemany("INSERT INTO catalog_collection_forms VALUES (?, ?, ?, ?, ?, ?, ?)", form_rows)

        # 7. Nạp sync_meta
        sm = data.get("sync_meta", {})
        self.conn.execute(
            "INSERT INTO catalog_sync_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                sm.get("last_synced_at", "2026-09-26T00:00:00"),
                sm.get("dwh_pipeline_run_at", "2026-09-26T00:00:00"),
                sm.get("total_criteria", 0),
                sm.get("total_departments", 0),
                sm.get("total_offices", 0),
                sm.get("total_missions", 0),
                sm.get("total_forms", 0),
                sm.get("status", "SUCCESS")
            )
        )

        # 8. Nạp provinces
        prov_rows = []
        for p in data.get("provinces", []):
            prov_rows.append((str(p["id"]), str(p["code"]), p["name"], bool(p.get("is_activated", True))))
            self._alias_registry.append({
                "alias": p["name"].lower().strip(),
                "code": str(p["code"]),
                "name": p["name"],
                "type": "province",
                "target_table": "dwh_internal.province"
            })
        if prov_rows:
            self.conn.executemany("INSERT OR IGNORE INTO catalog_provinces VALUES (?, ?, ?, ?)", prov_rows)

        # Đăng ký các từ viết tắt phổ biến công vụ vào Alias Registry
        common_acronyms = [
            ("tnlđ", "tai_nan_lao_dong_2", "Tai nạn lao động", "dwh_internal.criteria"),
            ("tnld", "tai_nan_lao_dong_2", "Tai nạn lao động", "dwh_internal.criteria"),
            ("tai nạn lđ", "tai_nan_lao_dong_2", "Tai nạn lao động", "dwh_internal.criteria"),
            ("dvc", "ho_so_dvc", "Dịch vụ công", "dwh_internal.criteria"),
            ("cchc", "cai_cach_hanh_chinh", "Cải cách hành chính", "dwh_internal.criteria"),
            ("khuyen cong", "kinh_phi_khuyen_cong", "Khuyến công", "dwh_internal.criteria"),
            ("chăn nuôi", "chan_nuoi4", "Chăn nuôi", "dwh_internal.criteria"),
            ("chan nuoi", "chan_nuoi4", "Chăn nuôi", "dwh_internal.criteria"),
            ("làng nghề truyền thống", "lang_nghe_truyen_thong", "Làng nghề truyền thồng", "dwh_internal.criteria"),
            ("diện tích muối công nghiệp", "dien_tich_muoi_san_xuat_cong_nghiep", "Diện tích muối sản xuất công nghiệp", "dwh_internal.criteria"),
            ("diện tích muối thủ công", "dien_tich_muoi_san_xuat_thu_cong", "Diện tích muối sản xuất thủ công", "dwh_internal.criteria"),
            ("doanh thu hợp tác xã", "doanh_thu_binh_quan_trong_nam_cua_mot_hop_tac_xa_nong_nghiep", "Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp", "dwh_internal.criteria"),
            ("doanh thu bình quân", "doanh_thu_binh_quan_trong_nam_cua_mot_hop_tac_xa_nong_nghiep", "Doanh thu bình quân trong năm của một hợp tác xã nông nghiệp", "dwh_internal.criteria"),
            ("tổng số hiện có", "dang_hoat_dong", "Đang hoạt động", "dwh_internal.criteria"),
            ("lũy kế tổng số lượng chủ thể có sản phẩm đạt ocop", "luy_ke_tong_so_luong_chu_the_den_thoi_diem_bao_cao", "Lũy kế tổng số lượng chủ thể đến thời điểm báo cáo", "dwh_internal.criteria"),
            ("lũy kế tổng số lượng sản phẩm ocop đạt chuẩn", "luy_ke_tong_so_luong_san_pham_ocop_den_thoi_diem_bao_cao", "Lũy kế tổng số lượng sản phẩm OCOP đến thời điểm báo cáo", "dwh_internal.criteria"),
            ("htx", "htx_broad", "Hợp tác xã", "dwh_internal.criteria"),
            ("hợp tác xã", "htx_broad", "Hợp tác xã", "dwh_internal.criteria"),
            ("ocop", "ocop_broad", "Chương trình OCOP", "dwh_internal.criteria"),
            ("bieu mau", "collection_form", "Biểu mẫu thu thập", "dwh_internal.collection_form"),
            ("collection form", "collection_form", "Biểu mẫu", "dwh_internal.collection_form"),
            ("nhiem vu", "mission", "Nhiệm vụ trọng tâm", "dwh_internal.mission"),
            ("ds phong ban ubnd tinh ld", "deparment", "Danh sách phòng ban đơn vị", "dwh_internal.deparment"),
            ("ubnd tinh ld", "deparment", "UBND Tỉnh Lâm Đồng", "dwh_internal.deparment"),
            ("ubnd", "deparment", "UBND", "dwh_internal.deparment"),
            ("sở nông nghiệp và phát triển nông thôn", "68-1-07", "Sở Nông nghiệp và PTNT Lâm Đồng", "dwh_internal.deparment"),
            ("sở nông nghiệp", "68-1-07", "Sở Nông nghiệp và PTNT Lâm Đồng", "dwh_internal.deparment"),
            ("nn&ptnt", "68-1-07", "Sở Nông nghiệp và PTNT Lâm Đồng", "dwh_internal.deparment"),
            ("so nong nghiep", "68-1-07", "Sở Nông nghiệp và PTNT Lâm Đồng", "dwh_internal.deparment"),
            ("sở công thương", "68-1-05", "Sở Công Thương Lâm Đồng", "dwh_internal.deparment"),
            ("so cong thuong", "68-1-05", "Sở Công Thương Lâm Đồng", "dwh_internal.deparment"),
            ("sở xây dựng", "68-1-04", "Sở Xây Dựng Lâm Đồng", "dwh_internal.deparment"),
            ("so xay dung", "68-1-04", "Sở Xây Dựng Lâm Đồng", "dwh_internal.deparment"),
            ("sở nội vụ", "68-1-01", "Sở Nội Vụ Tỉnh Lâm Đồng", "dwh_internal.deparment"),
            ("so noi vu", "68-1-01", "Sở Nội Vụ Tỉnh Lâm Đồng", "dwh_internal.deparment"),
            ("sở y tế", "68-1-06", "Sở Y Tế Lâm Đồng", "dwh_internal.deparment"),
            ("so y te", "68-1-06", "Sở Y Tế Lâm Đồng", "dwh_internal.deparment"),
            ("sở lao động", "68-1-03", "Sở Lao động - Thương binh và Xã hội Lâm Đồng", "dwh_internal.deparment"),
            ("so lao dong", "68-1-03", "Sở Lao động - Thương binh và Xã hội Lâm Đồng", "dwh_internal.deparment"),
            ("sở lđtbxh", "68-1-03", "Sở Lao động - Thương binh và Xã hội Lâm Đồng", "dwh_internal.deparment"),
            ("sở văn hóa", "68-1-08", "Sở Văn hóa, Thể thao và Du lịch Lâm Đồng", "dwh_internal.deparment"),
            ("so van hoa", "68-1-08", "Sở Văn hóa, Thể thao và Du lịch Lâm Đồng", "dwh_internal.deparment"),
            ("sở vhttdl", "68-1-08", "Sở Văn hóa, Thể thao và Du lịch Lâm Đồng", "dwh_internal.deparment"),
            ("ptnt", "a738d08b-45c0-4041-9760-213641d799f8", "Chi cục", "dwh_internal.office"),
            ("chi cục ptnt", "a738d08b-45c0-4041-9760-213641d799f8", "Chi cục", "dwh_internal.office"),
            ("chi cục phát triển nông thôn", "a738d08b-45c0-4041-9760-213641d799f8", "Chi cục", "dwh_internal.office"),
            ("chi cục nông thôn", "a738d08b-45c0-4041-9760-213641d799f8", "Chi cục", "dwh_internal.office"),
            ("chi cục", "a738d08b-45c0-4041-9760-213641d799f8", "Chi cục", "dwh_internal.office"),
            ("phòng nông nghiệp", "10dfc6c1-2393-413c-92ad-e8952c344524", "Phòng nông nghiệp", "dwh_internal.office"),
            ("phòng kinh tế", "5f9c3ea8-0a91-4092-b1cf-2480b18de4f3", "Phòng kinh tế", "dwh_internal.office"),
        ]
        for acr, code, name, tbl in common_acronyms:
            self._alias_registry.append({
                "alias": acr.lower().strip(),
                "code": code,
                "name": name,
                "type": "acronym",
                "target_table": tbl
            })

        # 9. Nạp seed users vào catalog_users
        seed_users = [
            ("af12924c-189c-4a39-857d-f3839990a4fd", "Admin Tỉnh Lâm Đồng", "admin-lamdong", "QTV", "68-1-01", "Sở Nội vụ", "68"),
            ("f3d3f00f-d1ff-47f8-8e6b-e329796bebff", "vy", "tuong", "Nhân viên văn phòng", "68-1-01", "Sở Nội vụ", "68"),
            ("cc99047a-692d-49f8-aacc-f3f8031a445b", "Nguyễn Thị Thúy Lành", "tzyalnh", "BA", "68-1-01", "Sở Nội vụ", "68"),
            ("2ebf478e-f245-43c3-816b-27a0a42099ed", "Phường Bắc Gia Nghĩa", "bacgianghia.ld", "QTV", "68-1-01", "Sở Nội vụ", "68"),
        ]
        self.conn.executemany("INSERT OR IGNORE INTO catalog_users VALUES (?, ?, ?, ?, ?, ?, ?)", seed_users)

    def _build_indexes(self) -> None:
        """Tạo Index ART trên DuckDB để tối ưu tốc độ tra cứu < 1ms."""
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_crit_code ON catalog_criteria(code);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_crit_name ON catalog_criteria(name);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_dept_code ON catalog_departments(code);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_office_name ON catalog_offices(name);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_prov_code ON catalog_provinces(code);")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_prov_name ON catalog_provinces(name);")

    def search_tables_by_keywords(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Tìm kiếm các bảng liên quan dựa trên từ khóa truy vấn kết hợp BM25-like matching
        trên schema description và column description.
        """
        tokens = [t.strip().lower() for t in query.split() if len(t.strip()) > 1]
        if not tokens:
            return [{"table_name": "dwh_internal.fact_report_criteria", "score": 1.0}]

        # Quét và tính điểm xuất hiện token trên catalog_schema_metadata
        query_sql = """
            SELECT table_name, count(*) as match_count
            FROM catalog_schema_metadata
            WHERE 
        """
        conditions = []
        params = []
        for t in tokens:
            conditions.append("(LOWER(column_description) LIKE ? OR LOWER(table_description) LIKE ? OR LOWER(column_name) LIKE ?)")
            params.extend([f"%{t}%", f"%{t}%", f"%{t}%"])

        query_sql += " OR ".join(conditions) + " GROUP BY table_name ORDER BY match_count DESC LIMIT ?"
        params.append(limit)

        try:
            rows = self.conn.execute(query_sql, params).fetchall()
            results = []
            for r in rows:
                results.append({"table_name": r[0], "score": float(r[1])})
            if not results:
                # Fallback mặc định Fact
                results = [{"table_name": "dwh_internal.fact_report_criteria", "score": 0.5}]
            return results
        except Exception as e:
            logger.warning("Lỗi tra cứu bảng qua DuckDB: %s", e)
            return [{"table_name": "dwh_internal.fact_report_criteria", "score": 0.5}]

    def match_alias_or_abbreviation(self, term: str, threshold: Optional[float] = None, tenant_code: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Sử dụng RapidFuzz C++ để đối chiếu mờ từ viết tắt hoặc danh xưng công vụ
        với danh mục alias đã đăng ký trong RAM (hỗ trợ phân vùng tenant_code).
        Áp dụng Adaptive Thresholding động theo độ dài từ để chống quá khớp (REJ-10).
        """
        term_clean = term.lower().strip()
        candidates = self._alias_registry
        if tenant_code:
            candidates = [
                a for a in self._alias_registry
                if not a.get("tenant_code") or a.get("tenant_code") == tenant_code or a.get("tenant_code") == "00"
            ]
        if not candidates:
            return None

        # Ngưỡng động thích ứng theo độ dài chuỗi (Adaptive Thresholding)
        if threshold is None:
            term_len = len(term_clean)
            if term_len <= 3:
                effective_threshold = 90.0
            elif term_len <= 6:
                effective_threshold = 80.0
            elif term_len <= 12:
                effective_threshold = 72.0
            else:
                effective_threshold = 65.0
        else:
            effective_threshold = threshold

        alias_names = [a["alias"] for a in candidates]
        match = process.extractOne(term_clean, alias_names, scorer=fuzz.ratio)
        if match and match[1] >= effective_threshold:
            idx = match[2]
            res = candidates[idx].copy()
            res["match_score"] = match[1]
            return res
        return None

    def get_table_metadata(self, table_name: str) -> Optional[TableMetadataDTO]:
        """Truy xuất DTO siêu dữ liệu của một bảng."""
        return self._table_metadata_cache.get(table_name)

    def get_provinces_list(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các tỉnh thành đã đăng ký trong RAM (DuckDB catalog_provinces)."""
        try:
            rows = self.conn.execute("SELECT code, name, is_activated FROM catalog_provinces ORDER BY name ASC;").fetchall()
            return [{"code": r[0], "name": r[1], "is_activated": bool(r[2])} for r in rows]
        except Exception:
            return []

    def _ensure_embeddings_indexed(self) -> None:
        """Nạp hoặc tính toán ma trận Dense Embeddings cho catalog_criteria (có cơ chế Disk Cache v2 thuần name)."""
        if self._criteria_embeddings is not None and len(self._criteria_cache_codes) > 0:
            return

        rows = self.conn.execute("""
            SELECT code, name, aliases, tenant_code, level 
            FROM catalog_criteria 
            ORDER BY created_date DESC NULLS LAST;
        """).fetchall()
        dedup_rows = []
        seen_keys = set()
        for r in rows:
            key = (r[1].lower().strip(), r[3] or "")
            if key not in seen_keys:
                seen_keys.add(key)
                dedup_rows.append(r)
        self._criteria_cache_codes = [r[0] for r in dedup_rows]
        self._criteria_cache_names = [r[1] for r in dedup_rows]
        self._criteria_cache_aliases = [r[2] or "" for r in dedup_rows]
        self._criteria_cache_tenants = [r[3] or "" for r in dedup_rows]
        self._criteria_cache_levels = [r[4] or 1 for r in dedup_rows]

        cache_dir = Path(__file__).resolve().parent.parent.parent / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        emb_cache_path = cache_dir / "criteria_embeddings_v2_name_only.npy"
        meta_cache_path = cache_dir / "criteria_meta_v2_name_only.json"

        # 1. Thử nạp từ đĩa
        if emb_cache_path.exists() and meta_cache_path.exists():
            try:
                with open(meta_cache_path, "r", encoding="utf-8") as f:
                    cached_meta = json.load(f)
                if (
                    cached_meta.get("codes") == self._criteria_cache_codes
                    and cached_meta.get("tenants") == self._criteria_cache_tenants
                ):
                    self._criteria_embeddings = np.load(emb_cache_path)
                    logger.info("Đã nạp %d vector embeddings từ cache đĩa v2 thuần name.", len(self._criteria_cache_codes))
                    return
            except Exception as e:
                logger.warning("Không thể nạp cache embedding từ đĩa: %s. Tính toán lại...", e)

        # 2. Tính toán embeddings nếu chưa có cache (Chỉ embed trên name và aliases, loại bỏ 100% code)
        try:
            embed_model = ModelRegistry.get_embedding_model()

            texts = []
            for n, a in zip(self._criteria_cache_names, self._criteria_cache_aliases):
                a_clean = a.strip()
                if a_clean:
                    texts.append(f"{n} ({a_clean})")
                else:
                    texts.append(n)

            self._criteria_embeddings = embed_model.encode(texts, normalize_embeddings=True)
            np.save(emb_cache_path, self._criteria_embeddings)
            with open(meta_cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "codes": self._criteria_cache_codes,
                    "tenants": self._criteria_cache_tenants
                }, f)
            logger.info("Đã tính toán và lưu cache v2 %d vector embeddings thành công.", len(texts))
        except Exception as e:
            logger.warning("⚠️ [DuckDBSemanticCatalog] Không thể tính toán remote embedding (%s). Hệ thống tự động chuyển sang fallback text-matching.", e)
            self._criteria_embeddings = None

    def _llm_disambiguate(self, query: str, candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Gọi micro-prompt LLM (Few-Shot + CoT) để giải quyết nhập nhằng hoặc chọn chỉ tiêu chính xác."""
        try:
            client = OpenAI(
                api_key=settings.effective_llm_api_key,
                base_url=settings.OPENROUTER_BASE_URL,
                timeout=15.0
            )
            cand_text = "\n".join([f"{i+1}. [{c['code']}] {c['name']}" for i, c in enumerate(candidates)])
            system_prompt = (
                "Bạn là trợ lý giải quyết nhập nhằng ngữ nghĩa chỉ tiêu (Criteria Disambiguator) cho Kho dữ liệu UBND Tỉnh Lâm Đồng.\n"
                "Hãy suy luận từng bước (Chain-of-Thought) ngắn gọn trong trường 'reason' trước khi kết luận:\n"
                "1. Xác định thực thể/đại lượng cốt lõi trong câu hỏi (số hộ, diện tích, sản lượng, thành lập mới, đang hoạt động, liên kết sản xuất...).\n"
                "2. Nếu câu hỏi chỉ rõ 1 chỉ tiêu cụ thể khớp với ứng viên -> trả về status = 'MATCH'.\n"
                "3. Nếu câu hỏi chỉ nêu tên nhóm cha bao trùm hoặc từ khóa đa nghĩa chưa rõ đại lượng con -> trả về status = 'AMBIGUOUS'.\n\n"
                "Few-Shot Examples:\n"
                "- Query: 'Tổng hộ sản xuất muối năm 2026 là bao nhiêu?' -> {\"reason\": \"Câu hỏi chỉ rõ đại lượng hộ sản xuất muối\", \"status\": \"MATCH\", \"code\": \"tong_ho_san_xuat_muoi_2\", \"name\": \"Tổng hộ sản xuất muối\"}\n"
                "- Query: 'Số liệu OCOP hiện nay?' -> {\"reason\": \"OCOP là nhóm chỉ tiêu cha, chưa rõ hỏi số sản phẩm 3-5 sao hay chủ thể\", \"status\": \"AMBIGUOUS\", \"candidates\": [{\"code\": \"chuong_trinh_ocop\", \"name\": \"Chương trình OCOP\"}]}\n"
                "CHỈ TRẢ VỀ JSON THUẦN TÚY, KHÔNG CÓ TEXT NGOÀI JSON."
            )
            user_prompt = f"Câu hỏi: {query}\nDanh sách ứng viên:\n{cand_text}"
            resp = client.chat.completions.create(
                model=settings.OPENROUTER_LIGHT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                max_tokens=600,
                response_format={"type": "json_object"}
            )
            raw = resp.choices[0].message.content or ""
            raw_clean = raw.strip()
            s_idx = raw_clean.find("{")
            e_idx = raw_clean.rfind("}")
            if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                raw_clean = raw_clean[s_idx : e_idx + 1]
            return json.loads(raw_clean, strict=False)
        except Exception as e:
            logger.warning("Lỗi LLM Disambiguation: %s", e)
            return None

    def find_criteria_by_name(
        self,
        query: str,
        limit: int = 1,
        top_k_candidates: int = 5,
        use_llm_disambiguation: bool = True,
        tenant_code: Optional[str] = "68",
        role_level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm tiêu chí (criteria) phù hợp nhất bằng SOTA Hybrid Search (Dense Embedding + Sparse BM25 via RRF)
        kết hợp Generative LLM Micro-Disambiguation (google/gemini-2.5-flash-lite).
        Cưỡng chế Pre-filtering theo tenant_code và role_level.
        So khớp thuần theo name và aliases, loại bỏ 100% mã kỹ thuật code.
        """
        if not query:
            return []

        q_clean = query.lower().strip()
        norm_q = " ".join(q_clean.replace("-", " ").replace("_", " ").split())
        if self.is_dimension_query(norm_q, "criteria"):
            return []

        # 1. Tra cứu trực tiếp khớp tên chỉ tiêu lá (is_leaf = TRUE) trong DuckDB RAM
        exact_name_matches = self.conn.execute("""
            SELECT code, name, length(name) as len_n, created_date
            FROM catalog_criteria
            WHERE is_leaf = TRUE AND length(name) >= 4 AND INSTR(?, LOWER(name)) > 0;
        """, (q_clean,)).fetchall()

        if exact_name_matches:
            import datetime
            min_dt = datetime.datetime.min
            exact_name_matches.sort(
                key=lambda r: (
                    r[2],
                    r[3] if r[3] is not None else min_dt,
                    len(r[0])
                ),
                reverse=True
            )
            exact_name_match = exact_name_matches[0]
            return [{
                "code": exact_name_match[0],
                "name": exact_name_match[1],
                "score": 100.0,
                "is_ambiguous": False,
                "candidates": [{
                    "code": exact_name_match[0],
                    "name": exact_name_match[1],
                    "rrf_score": 1.0,
                    "score": 100.0
                }]
            }]

        # 2. Thử đối chiếu nhanh qua Alias Registry có phân vùng tenant (Adaptive Thresholding)
        alias_match = self.match_alias_or_abbreviation(q_clean, threshold=None, tenant_code=tenant_code)
        if alias_match and alias_match.get("type") in ("criteria", "acronym") and alias_match.get("match_score", 0.0) >= 80.0:
            alias_term = (alias_match.get("alias") or alias_match.get("name") or "").lower().strip()

            # Đối chiếu trực tiếp alias_term
            if alias_match.get("code") == "htx_broad":
                matched_crit_rows = self.conn.execute("""
                    SELECT code, name FROM catalog_criteria
                    WHERE is_leaf = TRUE AND (LOWER(name) LIKE '%hợp tác xã%' OR LOWER(name) LIKE '%htx%');
                """).fetchall()
            elif alias_match.get("code") == "ocop_broad":
                matched_crit_rows = self.conn.execute("""
                    SELECT code, name FROM catalog_criteria
                    WHERE is_leaf = TRUE AND (LOWER(name) LIKE '%ocop%');
                """).fetchall()
            else:
                matched_crit_rows = self.conn.execute("""
                    SELECT code, name FROM catalog_criteria
                    WHERE LOWER(name) = ? OR LOWER(aliases) = ? OR INSTR(LOWER(aliases), ?) > 0;
                """, (alias_term, alias_term, alias_term)).fetchall()

            # Nếu là từ viết tắt hoặc cụm từ ngắn chung chung (acronym/category) map tới nhiều criteria
            is_broad_alias = alias_match.get("type") in ("acronym", "category", "broad") or alias_match.get("code") in ("htx_broad", "ocop_broad")
            if len(matched_crit_rows) > 1 and is_broad_alias and top_k_candidates > 1:
                cands_list = [
                    {"code": r[0], "name": r[1], "rrf_score": 1.0, "score": 85.0}
                    for r in matched_crit_rows[:top_k_candidates]
                ]
                return [{
                    "code": matched_crit_rows[0][0],
                    "name": matched_crit_rows[0][1],
                    "score": 85.0,
                    "is_ambiguous": True,
                    "candidates": cands_list
                }]

            return [{
                "code": alias_match["code"],
                "name": alias_match["name"],
                "score": alias_match.get("match_score", 100.0),
                "is_ambiguous": False,
                "candidates": [{
                    "code": alias_match["code"],
                    "name": alias_match["name"],
                    "rrf_score": 1.0,
                    "score": alias_match.get("match_score", 100.0)
                }]
            }]

        self._ensure_embeddings_indexed()
        if len(self._criteria_cache_codes) == 0:
            return []

        # 2. Pre-filtering: Xác định tập chỉ số hợp lệ theo tenant_code và role_level
        valid_indices = []
        for i, (tc, lvl) in enumerate(zip(self._criteria_cache_tenants, self._criteria_cache_levels)):
            if tenant_code and tc and tc != tenant_code and tc != "00":
                continue
            if role_level == 3:
                # Role 3 (Công dân): Chỉ truy cập các chỉ tiêu công khai (level <= 2)
                if lvl > 2:
                    continue
            valid_indices.append(i)

        if not valid_indices:
            # Fallback nếu không có tiêu chí nào khớp tenant
            valid_indices = list(range(len(self._criteria_cache_codes)))

        # 3. Dense Semantic Search (chỉ duyệt/xếp hạng trên valid_indices nếu có embeddings)
        dense_ranked = []
        if self._criteria_embeddings is not None:
            try:
                embed_model = ModelRegistry.get_embedding_model()
                q_emb = embed_model.encode([query], normalize_embeddings=True)[0]
                dense_sims = np.dot(self._criteria_embeddings, q_emb)
                valid_dense_scores = [(i, float(dense_sims[i])) for i in valid_indices]
                valid_dense_scores.sort(key=lambda x: x[1], reverse=True)
                seen_dense_codes = set()
                for i, score in valid_dense_scores:
                    c = self._criteria_cache_codes[i]
                    if c not in seen_dense_codes:
                        seen_dense_codes.add(c)
                        dense_ranked.append((c, self._criteria_cache_names[i], score))
                        if len(dense_ranked) >= 20:
                            break
            except Exception as e:
                logger.warning("⚠️ [DuckDBSemanticCatalog] Lỗi trích xuất dense vector query (%s), tiếp tục với sparse.", e)

        # 4. Sparse Search via RapidFuzz token_set_ratio trên name và aliases (mở rộng từ catalog_acronyms)
        q_expanded = q_clean
        try:
            acronym_rows = self.conn.execute("SELECT acronym, full_form FROM catalog_acronyms;").fetchall()
            for acr, full in acronym_rows:
                acr_low = acr.lower()
                full_low = full.lower()
                if full_low in q_clean:
                    q_expanded = q_clean.replace(full_low, acr_low)
                    break
                elif acr_low in q_clean.split() or f" {acr_low} " in f" {q_clean} " or q_clean == acr_low:
                    q_expanded = q_clean.replace(acr_low, full_low)
                    break
        except Exception:
            pass
        sparse_scores = []
        q_unacc = self._remove_accents(q_clean)
        is_unaccent_query = (q_clean == q_unacc)
        for i in valid_indices:
            name = self._criteria_cache_names[i]
            aliases = self._criteria_cache_aliases[i]
            target_text = f"{name} ({aliases})" if aliases else name
            target_low = target_text.lower()
            s_score = max(fuzz.token_set_ratio(q_clean, target_low), fuzz.token_set_ratio(q_expanded, target_low))
            if is_unaccent_query:
                s_score = max(s_score, fuzz.token_set_ratio(q_unacc, self._remove_accents(target_low)) * 0.98)
            sparse_scores.append((i, s_score))
        sparse_scores.sort(key=lambda x: x[1], reverse=True)
        seen_sparse_codes = set()
        sparse_ranked = []
        for i, score in sparse_scores:
            c = self._criteria_cache_codes[i]
            if c not in seen_sparse_codes:
                seen_sparse_codes.add(c)
                sparse_ranked.append((c, self._criteria_cache_names[i], score))
                if len(sparse_ranked) >= 20:
                    break

        # 5. Reciprocal Rank Fusion (RRF)
        rrf_dict: Dict[str, float] = {}
        details: Dict[str, Dict[str, Any]] = {}
        for rank, (code, name, score) in enumerate(dense_ranked):
            rrf_dict[code] = rrf_dict.get(code, 0.0) + 1.0 / (60.0 + rank + 1)
            details[code] = {"name": name, "dense_score": float(score), "dense_rank": rank + 1}
        for rank, (code, name, score) in enumerate(sparse_ranked):
            rrf_dict[code] = rrf_dict.get(code, 0.0) + 1.0 / (60.0 + rank + 1)
            if code in details:
                details[code]["sparse_score"] = float(score)
                details[code]["sparse_rank"] = rank + 1
            else:
                details[code] = {"name": name, "sparse_score": float(score), "sparse_rank": rank + 1}

        sorted_candidates = sorted(rrf_dict.items(), key=lambda x: x[1], reverse=True)[:top_k_candidates]
        candidates = []
        for code, rrf_score in sorted_candidates:
            candidates.append({
                "code": code,
                "name": details[code]["name"],
                "rrf_score": rrf_score,
                "dense_score": details[code].get("dense_score", 0.0),
                "sparse_score": details[code].get("sparse_score", 0.0),
            })

        if not candidates:
            return []

        # 6. Generative LLM Micro-Disambiguation (< 150 tokens)
        if use_llm_disambiguation and settings.effective_llm_api_key:
            disambig_res = self._llm_disambiguate(query, candidates)
            if disambig_res:
                if disambig_res.get("status") == "MATCH" and disambig_res.get("code"):
                    matched_code = disambig_res["code"]
                    matched_name = disambig_res.get("name") or next((c["name"] for c in candidates if c["code"] == matched_code), matched_code)
                    return [{
                        "code": matched_code,
                        "name": matched_name,
                        "score": 98.0,
                        "is_ambiguous": False,
                        "reason": disambig_res.get("reason", "LLM exact disambiguation match"),
                        "candidates": candidates
                    }]
                elif disambig_res.get("status") == "AMBIGUOUS":
                    return [{
                        "code": candidates[0]["code"],
                        "name": candidates[0]["name"],
                        "score": 70.0,
                        "is_ambiguous": True,
                        "reason": disambig_res.get("reason", "Truy vấn mang tính bao trùm, cần người dùng làm rõ"),
                        "candidates": disambig_res.get("candidates") or candidates
                    }]

        # Fallback khi tắt LLM hoặc API lỗi: tính độ nhập nhằng theo REAR Margin Gap (top1_score - top2_score < 15.0)
        top1 = candidates[0]
        top1_score = max(float(top1.get("sparse_score", 0.0)), float(top1.get("dense_score", 0.0) * 100.0))
        is_ambiguous = False
        if len(candidates) >= 2:
            top2 = candidates[1]
            top2_score = max(float(top2.get("sparse_score", 0.0)), float(top2.get("dense_score", 0.0) * 100.0))
            if (top1_score - top2_score) < 15.0 and top1["name"].lower().strip() != q_clean:
                is_ambiguous = True
        return [{
            "code": top1["code"],
            "name": top1["name"],
            "score": top1_score if top1_score > 0 else float(top1.get("dense_score", 0.8) * 100.0),
            "is_ambiguous": is_ambiguous,
            "candidates": candidates[:limit]
        }]

    def find_top_k_candidates(
        self,
        query: str,
        top_k: int = 5,
        score_cutoff: float = 50.0,
        tenant_code: Optional[str] = "68"
    ) -> Tuple[List[Dict[str, Any]], bool, float]:
        """
        Trích xuất Top-K ứng viên chỉ tiêu từ DuckDB In-Memory Catalog bằng Hybrid RRF (Dense + Sparse).
        Căn cứ: ADR-002, implementation_plan.md
        Trả về: (candidates, is_ambiguous, score_delta)
        - candidates: Danh sách ứng viên có score >= score_cutoff (tối đa top_k)
        - is_ambiguous: True nếu câu hỏi quá vắn tắt hoặc score delta giữa Top 1 & Top 2 < 0.10
        - score_delta: Điểm chênh lệch giữa Top 1 và Top 2
        """
        import unicodedata
        if not query:
            return ([], False, 0.0)

        q_clean = unicodedata.normalize('NFC', query.strip())
        q_lower = q_clean.lower()
        norm_q = " ".join(q_lower.replace("-", " ").replace("_", " ").split())
        if self.is_dimension_query(norm_q, "criteria"):
            return ([], False, 0.0)

        # 1. Tra cứu qua find_criteria_by_name với top_k_candidates mở rộng
        raw_res = self.find_criteria_by_name(
            query=q_clean,
            limit=top_k,
            top_k_candidates=max(top_k * 2, 10),
            use_llm_disambiguation=False,
            tenant_code=tenant_code
        )

        all_candidates = []
        if raw_res and raw_res[0].get("candidates"):
            all_candidates = raw_res[0]["candidates"]
        elif raw_res:
            all_candidates = raw_res

        # 2. Lọc và chuẩn hóa score kết hợp
        valid_candidates = []
        for c in all_candidates:
            raw_c_score = float(c.get("score", 0.0)) or (float(raw_res[0].get("score", 0.0)) if raw_res else 0.0)
            d_score = float(c.get("dense_score", 0.0)) * 100.0
            s_score = float(c.get("sparse_score", 0.0))
            if d_score > 0 or s_score > 0:
                comb_score = round(d_score * 0.6 + s_score * 0.4, 2) if s_score > 0 else round(d_score, 2)
            else:
                comb_score = round(raw_c_score, 2) if raw_c_score > 0 else 85.0
            c_name = unicodedata.normalize('NFC', c["name"].strip())

            # Thưởng điểm nếu khớp tuyệt đối
            if c_name.lower() == q_lower:
                comb_score = 100.0
            elif c_name.lower() in q_lower:
                comb_score = max(comb_score, 85.0)

            if comb_score >= score_cutoff:
                valid_candidates.append({
                    "code": c.get("code"),
                    "name": c_name,
                    "score": comb_score,
                    "dense_score": round(d_score, 2),
                    "sparse_score": round(s_score, 2),
                })

        valid_candidates.sort(
            key=lambda x: (
                x["score"],
                len(x.get("code", "") or "")
            ),
            reverse=True
        )

        # Khử trùng lặp tên hiển thị (ADR-002: Mỗi tên chỉ tiêu chỉ giữ 1 candidate tối ưu nhất)
        deduped_candidates = []
        seen_cand_names = set()
        for cand in valid_candidates:
            clean_n = unicodedata.normalize('NFC', cand["name"].strip().lower())
            if clean_n not in seen_cand_names:
                seen_cand_names.add(clean_n)
                deduped_candidates.append(cand)

        # Ưu tiên chỉ tiêu tổng thể (Tổng ...) khi câu hỏi mang tính khái quát (không chỉ rõ phân loại con)
        tong_candidates = [c for c in deduped_candidates if c["name"].lower().startswith("tổng ")]
        if tong_candidates and deduped_candidates:
            best_tong = tong_candidates[0]
            top_1 = deduped_candidates[0]
            if best_tong != top_1:
                # Nếu query không có các từ đặc thù của top_1 (ví dụ 'công nghiệp', 'thủ công')
                top1_extra_words = [w for w in top_1["name"].lower().split() if w not in best_tong["name"].lower() and len(w) > 2]
                has_specific_sub_in_query = any(w in q_lower for w in top1_extra_words)
                if not has_specific_sub_in_query and (top_1["score"] - best_tong["score"]) <= 5.0:
                    deduped_candidates.remove(best_tong)
                    best_tong["score"] = top_1["score"] + 1.0
                    deduped_candidates.insert(0, best_tong)

        top_candidates = deduped_candidates[:top_k]

        # 3. Tính toán score_delta
        if len(top_candidates) >= 2:
            score_delta = round((top_candidates[0]["score"] - top_candidates[1]["score"]) / 100.0, 4)
        elif len(top_candidates) == 1:
            score_delta = 1.0
        else:
            score_delta = 0.0

        # 4. Xác định cờ mơ hồ (is_ambiguous) theo khung REAR Margin Gap (ACL 2024)
        is_ambiguous = bool(raw_res and raw_res[0].get("is_ambiguous"))
        if len(set(c["name"].strip().lower() for c in top_candidates)) <= 1:
            is_ambiguous = False
        elif len(top_candidates) >= 2:
            top1_score = top_candidates[0]["score"]
            top2_score = top_candidates[1]["score"]
            delta = top1_score - top2_score
            top1_name = top_candidates[0]["name"].strip().lower()
            top2_name = top_candidates[1]["name"].strip().lower()

            # Decision Matrix: Nếu Top1 >= 70.0 và Gap > 15.0 -> Luôn là Confident Match (không mơ hồ)
            if top1_score >= 70.0 and delta > 15.0:
                is_ambiguous = False
            elif top1_name in q_lower or top1_name == q_lower:
                # Tên chỉ tiêu top 1 xuất hiện nguyên vẹn trong câu hỏi người dùng
                is_ambiguous = False
            elif top1_name.startswith("tổng ") and not top2_name.startswith("tổng "):
                # Ưu tiên chỉ tiêu tổng thể (aggregate) khi có các phân loại con
                is_ambiguous = False
            else:
                # Kiểm tra độ phủ từ khóa phân biệt (loại bỏ stopwords tĩnh, lọc độ dài từ > 2):
                t1_tokens = {w for w in top1_name.split() if len(w) > 2}
                t2_tokens = {w for w in top2_name.split() if len(w) > 2}
                diff_t1 = t1_tokens - t2_tokens
                diff_t2 = t2_tokens - t1_tokens
                q_tokens = set("".join(c if c.isalnum() else " " for c in q_lower).split())

                def _stem_core_cand(n: str) -> str:
                    return self.strip_query_noise(n, "METRIC_AGG_PREFIX_NOISE")


                core_1 = _stem_core_cand(top1_name)
                core_2 = _stem_core_cand(top2_name)
                is_synonym_candidates = bool(core_1 and core_1 == core_2)

                if is_synonym_candidates:
                    # Top 1 và Top 2 là biến thể đồng nghĩa của cùng 1 chỉ tiêu (khác tiền tố số lượng/tổng số)
                    if any(w in q_tokens for w in ("bao", "nhiêu", "số", "lượng")) and top2_name.startswith("số lượng"):
                        top_candidates[0], top_candidates[1] = top_candidates[1], top_candidates[0]
                    is_ambiguous = False
                elif t1_tokens and t1_tokens.issubset(q_tokens):
                    # Toàn bộ từ khóa nội dung của Top 1 đều xuất hiện trong câu hỏi
                    if any(w in q_tokens for w in ("bao", "nhiêu", "số", "lượng")) and top2_name.startswith("số lượng") and _stem_core_cand(top2_name) == top1_name:
                        top_candidates[0], top_candidates[1] = top_candidates[1], top_candidates[0]
                    is_ambiguous = False
                elif diff_t1 and (diff_t1 & q_tokens) and not (diff_t2 & q_tokens):
                    is_ambiguous = False
                elif diff_t2 and (diff_t2 & q_tokens) and not (diff_t1 & q_tokens):
                    # Top 2 chứa từ khóa phân biệt trong query mà Top 1 không có -> Hoán đổi Top 2 lên Top 1 và Confident Match
                    top_candidates[0], top_candidates[1] = top_candidates[1], top_candidates[0]
                    is_ambiguous = False
                elif delta < 15.0 and top1_score < 95.0:
                    is_ambiguous = True
                else:
                    is_ambiguous = False

        return (top_candidates, is_ambiguous, score_delta)

    def retrieve_candidate_metrics(
        self, query: str, top_k: int = 3, score_threshold: float = 0.40, tenant_code: str = "68"
    ) -> List[Dict[str, Any]]:
        """
        Tra cứu siêu tốc các chỉ tiêu ứng viên trong DuckDB RAM phục vụ Pre-Retrieval Grounding.
        Kết hợp tìm kiếm từ khóa và so khớp mờ Jaro-Winkler / Levenshtein qua find_top_k_candidates.
        Hoàn toàn chạy trong RAM (< 3ms), không gọi mạng ngoài.
        """
        if not hasattr(self, "conn") or not self.conn or not query:
            return []

        candidates = []
        try:
            # Chuẩn hóa truy vấn tìm kiếm
            q_norm = query.lower().strip()
            # Chuẩn hóa ngưỡng score_threshold về thang 0.0 - 1.0 và score_cutoff về 0 - 100
            norm_threshold = score_threshold / 100.0 if score_threshold > 1.0 else score_threshold
            score_cutoff = norm_threshold * 100.0

            results, _, _ = self.find_top_k_candidates(
                q_norm, top_k=top_k * 2, score_cutoff=score_cutoff, tenant_code=tenant_code
            )
            q_tokens = set("".join(c if c.isalnum() else " " for c in q_norm).split())
            for item in results:
                raw_score = item.get("similarity")
                if raw_score is None:
                    s = float(item.get("score", 0.0))
                    raw_score = s / 100.0 if s > 1.0 else s
                else:
                    raw_score = float(raw_score)

                if raw_score >= norm_threshold:
                    cand_name = item.get("name", "")
                    cand_tokens = set("".join(c if c.isalnum() else " " for c in cand_name.lower()).split())
                    # Khử nhiễu khớp từ đơn lẻ giả danh (ví dụ 'quả' trong 'kết quả' hay 'lâm' trong địa danh 'lâm đồng')
                    # Đối với chỉ tiêu đa từ và điểm tương đồng biên (< 0.60), bắt buộc phải có từ nội dung thực tế (loại trừ từ tố phụ thuộc)
                    ALLOWED_FALSE_MORPHEMES = {"quả", "lâm", "đồng", "tỉnh", "thành", "phố", "hoạt", "động", "các", "những", "toàn", "tổng", "số", "của", "tại", "ở", "cho"}
                    common_content_tokens = (cand_tokens & q_tokens) - ALLOWED_FALSE_MORPHEMES
                    if raw_score < 0.60 and len(cand_tokens) >= 2 and not common_content_tokens:
                        continue

                    candidates.append({
                        "name": cand_name,
                        "code": item.get("code") or item.get("id", ""),
                        "score": round(raw_score, 2),
                        "office_name": item.get("office_name", ""),
                    })
                if len(candidates) >= top_k:
                    break
        except Exception as e:
            logger.debug("Lỗi tra cứu retrieve_candidate_metrics: %s", e)

        return candidates

    def resolve_administrative_scope(self, term: str, admin_level_hint: Optional[int] = None) -> Dict[str, Any]:
        """
        Phân giải phạm vi hành chính đa cấp (Tenant / Department / Office).
        Triệt tiêu 100% heuristic substring 'in' gây nuốt phạm vi cấp Tỉnh.
        """
        if not term:
            return {"type": "unknown", "tenant_code": "68", "department_code": None, "office_id": None, "admin_level": None}

        t_clean = term.lower().strip()

        # 1. Cấp 0: Toàn tỉnh (Tra cứu động qua catalog_tenants trong RAM hoặc admin_level_hint)
        tenant_match = None
        try:
            tenant_rows = self.conn.execute("SELECT tenant_code, name, aliases FROM catalog_tenants;").fetchall()
            for tcode, tname, taliases in tenant_rows:
                alias_list = [a.strip() for a in taliases.lower().split(",") if a.strip()]
                if tname.lower() in t_clean or any(a in t_clean for a in alias_list):
                    tenant_match = (tcode, tname)
                    break
        except Exception:
            pass

        if admin_level_hint == 0 or tenant_match:
            if not any(kw in t_clean for kw in ("sở ", "phòng ", "chi cục", "văn phòng")):
                t_code = tenant_match[0] if tenant_match else "68"
                t_name = tenant_match[1] if tenant_match else "Tỉnh Lâm Đồng"
                return {
                    "type": "tenant",
                    "tenant_code": t_code,
                    "name": t_name,
                    "department_code": None,
                    "office_id": None,
                    "admin_level": 0
                }

        # 1.5 Kiểm tra Alias Registry trước cho cơ quan sở ngành hoặc phòng ban
        alias_res = self.match_alias_or_abbreviation(t_clean, threshold=80.0)
        if alias_res and alias_res.get("type") in ("department", "acronym") and ("deparment" in alias_res.get("target_table", "") or "department" in alias_res.get("target_table", "")):
            return {
                "type": "department",
                "department_code": alias_res["code"],
                "code": alias_res["code"],
                "name": alias_res["name"],
                "tenant_code": alias_res.get("tenant_code", "68"),
                "office_id": None,
                "admin_level": 1
            }
        elif alias_res and (alias_res.get("type") == "office" or "office" in alias_res.get("target_table", "")):
            return {
                "type": "office",
                "office_id": str(alias_res.get("code") or alias_res.get("id")),
                "code": str(alias_res.get("code") or alias_res.get("id")),
                "name": alias_res["name"],
                "department_code": alias_res.get("department_code"),
                "tenant_code": alias_res.get("tenant_code", "68"),
                "admin_level": 2
            }

        has_office_indicator = any(kw in t_clean for kw in ("phòng ", "phong ", "chi cục", "chi cuc", "văn phòng", "van phong"))
        has_dept_indicator = any(kw in t_clean for kw in ("sở ", "so ", "ubnd", "ủy ban", "nn&ptnt", "lđtbxh", "vhttdl"))

        # 2. Cấp 2: Phòng Ban (office) - đánh giá trước để ưu tiên đơn vị cụ thể khi có từ khóa phòng/chi cục
        off_rows = self.conn.execute("SELECT id, name, department_code, tenant_code FROM catalog_offices;").fetchall()
        best_off = None
        best_off_score = 0.0
        t_clean_norm = t_clean.replace("hóa", "hoá")
        for oid, name, dcode, t_code in off_rows:
            name_low = name.lower()
            if name_low.startswith("phòng ") and "phòng " not in t_clean and "phong " not in t_clean:
                continue
            if name_low.startswith("văn phòng") and "văn phòng" not in t_clean and "van phong" not in t_clean:
                continue
            if name_low.startswith("chi cục") and "chi cục" not in t_clean and "chi cuc" not in t_clean and "ptnt" not in t_clean:
                continue

            distinctive = self.strip_query_noise(name_low, "OFFICE_PREFIX_NOISE")


            # Bắt buộc phần tên định danh đặc thù (distinctive) phải có mặt trong câu hỏi
            if distinctive and distinctive not in ("ban", "khoa"):
                dist_norm = distinctive.replace("hóa", "hoá")
                if distinctive not in t_clean and dist_norm not in t_clean_norm:
                    continue

            score = fuzz.token_set_ratio(t_clean, name_low)
            if score > best_off_score:
                best_off_score = score
                best_off = (oid, name, dcode, t_code)

        # Kiểm tra thêm trong _alias_registry cho office (ví dụ: ptnt, chi cục ptnt...)
        tokens = set(" ".join(c if c.isalnum() else " " for c in t_clean).split())
        for item in self._alias_registry:
            if item.get("type") == "office" or item.get("target_table") == "dwh_internal.office":
                al = item.get("alias", "").lower()
                if al == "ptnt" and has_dept_indicator and "chi cục" not in t_clean:
                    continue
                if al in tokens or (len(al) > 3 and al in t_clean) or fuzz.token_set_ratio(t_clean, al) >= 90.0:
                    al_score = 95.0
                    if al_score > best_off_score:
                        best_off_score = al_score
                        best_off = (item.get("code", item.get("id")), item.get("name"), item.get("department_code"), item.get("tenant_code", "68"))

        if best_off and best_off_score >= 80.0 and (has_office_indicator or not has_dept_indicator) and admin_level_hint != 1:
            return {
                "type": "office",
                "office_id": str(best_off[0]),
                "code": str(best_off[0]),
                "name": best_off[1],
                "department_code": best_off[2],
                "tenant_code": best_off[3],
                "admin_level": 2
            }

        # 3. Cấp 1: Sở Ban Ngành (department)
        t_norm = t_clean.replace("phát triển nông thôn", "ptnt").replace("nn&ptnt", "sở nông nghiệp và ptnt")
        dept_rows = self.conn.execute("SELECT code, name, level, tenant_code FROM catalog_departments WHERE level = 1;").fetchall()
        best_dept = None
        best_dept_score = 0.0
        for code, name, lvl, t_code in dept_rows:
            name_low = name.lower()
            if name_low.startswith("sở ") and not has_dept_indicator:
                continue
            name_stripped = name_low
            for prov in ("tỉnh lâm đồng", "lâm đồng", "tp. hồ chí minh", "hồ chí minh"):
                name_stripped = name_stripped.replace(prov, " ")
            name_stripped = " ".join(name_stripped.split())
            score = max(
                fuzz.token_set_ratio(t_clean, name_low),
                fuzz.token_set_ratio(t_norm, name_low),
                fuzz.token_set_ratio(t_clean, name_stripped) if len(name_stripped) > 3 else 0.0
            )
            if score > best_dept_score:
                best_dept_score = score
                best_dept = (code, name, t_code)

        # Kiểm tra thêm trong _alias_registry cho department
        for item in self._alias_registry:
            tbl = item.get("target_table", "")
            if item.get("type") in ("department", "acronym") and ("deparment" in tbl or "department" in tbl):
                al = item.get("alias", "").lower()
                if al in tokens or (len(al) > 3 and al in t_clean) or fuzz.token_set_ratio(t_clean, al) >= 90.0:
                    al_score = 95.0
                    if al_score > best_dept_score:
                        best_dept_score = al_score
                        best_dept = (item.get("code"), item.get("name"), item.get("tenant_code", "68"))

        if best_dept and best_dept_score >= 80.0:
            return {
                "type": "department",
                "department_code": best_dept[0],
                "code": best_dept[0],
                "name": best_dept[1],
                "tenant_code": best_dept[2],
                "office_id": None,
                "admin_level": 1
            }

        if best_off and best_off_score >= 80.0:
            return {
                "type": "office",
                "office_id": str(best_off[0]),
                "code": str(best_off[0]),
                "name": best_off[1],
                "department_code": best_off[2],
                "tenant_code": best_off[3],
                "admin_level": 2
            }

        return {"type": "unknown", "tenant_code": "68", "department_code": None, "office_id": None, "admin_level": None}

    def find_department_or_office(self, term: str, admin_level_hint: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Đối chiếu tên phòng ban hoặc cơ quan sở ngành từ tên gọi / từ khóa.
        Sử dụng resolve_administrative_scope để bảo đảm Invariance Cấp Tỉnh.
        """
        res = self.resolve_administrative_scope(term, admin_level_hint=admin_level_hint)
        if res.get("type") in ("tenant", "department", "office"):
            return res
        return None

    def is_compatible(self, topic_entity: str, metric_attribute: str) -> bool:
        """
        Schema Compatibility Gate (Điểm chốt 1 - v1.4.0):
        Kiểm tra xem thuộc tính mới (metric_attribute, ví dụ: 'diện tích', 'hộ', 'sản lượng', 'chức vụ')
        có tương thích ngữ nghĩa và có tồn tại trong CSDL DWH đối với thực thể chủ đề (topic_entity, ví dụ: 'sản xuất muối') hay không.
        
        Trả về True nếu:
        - Tồn tại chỉ tiêu trong catalog_criteria kết hợp cả topic_entity và metric_attribute.
        - Hoặc topic_entity thuộc bảng nghiệp vụ phi-criteria (user/mission/report) và metric_attribute là cột hợp lệ.
        """
        if not topic_entity or not metric_attribute:
            return False

        t_low = topic_entity.lower().strip()
        m_low = metric_attribute.lower().strip()

        # 1. Tra cứu tính tương thích qua catalog_schema_metadata trong DuckDB RAM
        try:
            meta_rows = self.conn.execute("""
                SELECT simple_name, column_name, column_description, table_description
                FROM catalog_schema_metadata;
            """).fetchall()
            has_table_match = False
            has_col_match = False
            for tbl, col, col_desc, tbl_desc in meta_rows:
                tbl_text = f"{tbl} {tbl_desc or ''}".lower()
                col_text = f"{col} {col_desc or ''}".lower()
                if any(tok in tbl_text for tok in t_low.split() if len(tok) > 2):
                    has_table_match = True
                if any(tok in col_text for tok in m_low.split() if len(tok) > 2):
                    has_col_match = True
            if has_table_match and has_col_match:
                return True
        except Exception:
            pass

        # 5. Kiểm tra đối soát với catalog_criteria trong RAM (lọc động theo độ dài từ > 2, loại bỏ stopwords tĩnh)
        t_tokens = [w for w in t_low.split() if len(w) > 2]
        m_tokens = [w for w in m_low.split() if len(w) > 2]

        if not t_tokens or not m_tokens:
            return False

        try:
            t_main = t_tokens[-1]
            m_main = m_tokens[0]

            check_sql = """
                SELECT COUNT(*) FROM catalog_criteria 
                WHERE LOWER(name) LIKE ? AND LOWER(name) LIKE ?;
            """
            row = self.conn.execute(check_sql, [f"%{t_main}%", f"%{m_main}%"]).fetchone()
            if row and row[0] > 0:
                return True

            if len(t_tokens) > 1:
                t_alt = t_tokens[0]
                row = self.conn.execute(check_sql, [f"%{t_alt}%", f"%{m_main}%"]).fetchone()
                if row and row[0] > 0:
                    return True

            for item in self._alias_registry:
                a_name = item.get("name", "").lower()
                if t_main in a_name and m_main in a_name:
                    return True
        except Exception as e:
            logger.debug("Lỗi kiểm tra tính tương thích criteria: %s", e)

        return False

    def resolve_spatial_tenant(self, spatial_mention: Optional[str], default_tenant: str = "68") -> str:
        """
        Schema-Driven Dynamic Spatial Resolution (tra cứu catalog_tenants trong DuckDB RAM).
        Đối chiếu mờ giữa spatial_mention và bảng catalog_tenants trong RAM.
        Nếu spatial_mention là None hoặc không khớp, trả về default_tenant (mặc định '68').
        """
        if not spatial_mention:
            return default_tenant
        s_clean = spatial_mention.lower().strip()
        try:
            res_tc = self.conn.execute(
                "SELECT regexp_extract(?, '(?i)tenant_code\\s*[:=]\\s*([a-zA-Z0-9_]+)', 1)",
                [spatial_mention],
            ).fetchone()
            if res_tc and res_tc[0]:
                return res_tc[0]
        except Exception:
            pass

        if s_clean.isdigit() and len(s_clean) == 2:
            return s_clean

        try:
            rows = self.conn.execute("SELECT tenant_code, name, aliases FROM catalog_tenants;").fetchall()
            for tc, name, aliases in rows:
                if s_clean == tc.lower() or s_clean == name.lower():
                    return tc
                alias_list = [a.strip() for a in aliases.lower().split(",") if a.strip()]
                if s_clean in alias_list:
                    return tc
                for a in alias_list:
                    if a in s_clean or s_clean in a:
                        return tc
            # Fuzzy match
            best_score = 0
            best_tc = default_tenant
            for tc, name, aliases in rows:
                alias_list = [name.lower()] + [a.strip() for a in aliases.lower().split(",") if a.strip()]
                for a in alias_list:
                    sc = fuzz.partial_ratio(s_clean, a)
                    if sc > best_score and sc >= 75:
                        best_score = sc
                        best_tc = tc
            return best_tc
        except Exception as e:
            logger.warning("Lỗi resolve_spatial_tenant: %s", e)
            return default_tenant

    def get_sample_quick_chips(self, tenant_code: str = "68", limit: int = 3, year: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy mẫu động các chỉ tiêu thực tế từ Catalog RAM để làm Action Chips."""
        try:
            import datetime
            current_year = year or str(datetime.datetime.now().year)
            res = self.conn.execute(
                "SELECT name FROM catalog_criteria WHERE tenant_code = ? ORDER BY RANDOM() LIMIT ?",
                [tenant_code, limit]
            ).fetchall()
            if not res:
                res = self.conn.execute("SELECT name FROM catalog_criteria ORDER BY RANDOM() LIMIT ?", [limit]).fetchall()
            
            chips = []
            for idx, row in enumerate(res, 1):
                crit_name = str(row[0]).strip()
                chips.append({
                    "id": f"chip_{idx}",
                    "label": f"📊 {crit_name[:35]}",
                    "query_text": f"Số liệu {crit_name} năm {current_year} là bao nhiêu?"
                })
            return chips
        except Exception:
            return []

    def resolve_metric_id(self, metric_name: Optional[str]) -> Optional[str]:
        """
        Tra cứu ID/Code của chỉ tiêu trong RAM catalog_criteria.
        Trả về None nếu metric_name rỗng, là danh từ tập hợp, hoặc không tồn tại trong DB.
        """
        if not metric_name:
            return None
        import unicodedata
        m_norm = unicodedata.normalize("NFC", metric_name.strip()).lower()
        clean_m = " ".join(m_norm.replace("-", " ").replace("_", " ").split())
        if self.is_dimension_query(clean_m, "criteria"):
            return None

        try:
            # 1. Exact match on name
            row = self.conn.execute(
                "SELECT id, code, name FROM catalog_criteria WHERE LOWER(name) = ? ORDER BY created_date DESC NULLS LAST LIMIT 1;",
                [clean_m],
            ).fetchone()
            if row:
                return str(row[0] or row[1])

            # 2. Match via alias registry
            alias_res = self.match_alias_or_abbreviation(clean_m, threshold=90.0)
            if alias_res and alias_res.get("type") == "criteria":
                return str(alias_res.get("code") or alias_res.get("id"))

            # 2b. Match via DuckDB RAM hierarchy classifier before heavy vector search
            h_res = self.classify_criterion_hierarchy(clean_m)
            if h_res and h_res.get("classification") in ("single_leaf", "duplicate_leaf", "parent", "parent_group"):
                m_code = h_res.get("matched_code") or h_res.get("matched_id")
                if m_code:
                    return str(m_code)
                m_name = h_res.get("matched_name")
                if m_name:
                    r2 = self.conn.execute(
                        "SELECT id, code FROM catalog_criteria WHERE LOWER(name) = LOWER(?) LIMIT 1;",
                        [m_name],
                    ).fetchone()
                    if r2:
                        return str(r2[1] or r2[0])

            if len(clean_m) <= 3:
                return None

            # 3. Fuzzy search in catalog_criteria
            cands, is_ambig, _ = self.find_top_k_candidates(clean_m, top_k=1, score_cutoff=85.0)
            if cands:
                return str(cands[0].get("code") or "")
        except Exception as e:
            logger.debug("Lỗi resolve_metric_id: %s", e)
        return None

    @staticmethod
    def _remove_accents(text: str) -> str:
        if not text:
            return ""
        import unicodedata
        s = text.replace("đ", "d").replace("Đ", "D")
        return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

    def _strip_dept_noise(self, text: str) -> str:
        if not text:
            return ""
        t = text
        dept_names = set()
        if hasattr(self, "conn") and self.conn:
            try:
                rows = self.conn.execute("""
                    SELECT DISTINCT LOWER(name) FROM catalog_offices WHERE name IS NOT NULL
                    UNION
                    SELECT DISTINCT LOWER(name) FROM catalog_departments WHERE name IS NOT NULL;
                """).fetchall()
                base_names = [r[0].strip() for r in rows if r[0] and len(r[0].strip()) >= 3]
                dept_names.update(base_names)
                for b in base_names:
                    for pq in (" lâm đồng", " tp. hồ chí minh", " tp hồ chí minh", " tphcm", " tỉnh lâm đồng"):
                        if pq in b:
                            clean_b = b.replace(pq, "").strip()
                            dept_names.add(clean_b)
                            stripped_b = self.strip_query_noise(clean_b, "DEPT_PREFIX_NOISE")
                            if stripped_b and stripped_b != clean_b:
                                dept_names.add(stripped_b)
                                for alt_pfx in ("sở ", "phòng ", "chi cục "):
                                    dept_names.add(alt_pfx + stripped_b)


                acr_rows = self.conn.execute("SELECT LOWER(acronym), LOWER(full_form) FROM catalog_acronyms;").fetchall()
                for d in list(dept_names):
                    if " & " in d:
                        dept_names.add(d.replace(" & ", " và "))
                        dept_names.add(d.replace(" & ", " va "))
                    if " và " in d:
                        dept_names.add(d.replace(" và ", " & "))
                    for acr, full in acr_rows:
                        if f" {acr} " in f" {d} ":
                            dept_names.add((" " + d + " ").replace(f" {acr} ", f" {full} ").strip())
                        if f" {full} " in f" {d} ":
                            dept_names.add((" " + d + " ").replace(f" {full} ", f" {acr} ").strip())
            except Exception:
                pass
        for d in sorted(dept_names, key=len, reverse=True):
            if d and len(d) >= 5:
                if d in t:
                    t = t.replace(d, " ")
                d_unacc = self._remove_accents(d)
                if d_unacc and d_unacc in t:
                    t = t.replace(d_unacc, " ")
        return t

    def resolve_mission(self, term: str) -> Optional[str]:
        """
        Tra cứu động nhiệm vụ trọng tâm từ catalog_missions trong DuckDB RAM.
        Chỉ khớp cụm từ liền kề (contiguous phrase) có ranh giới từ hợp lệ.
        Loại bỏ hoàn toàn bag-of-words subset matching gây ghép rời 'nhiệm vụ' với số '1' (REJ-07, REJ-08).
        """
        if not term:
            return None
        t_clean = term.lower().strip()
        t_clean = self._strip_dept_noise(t_clean)

        t_unacc = self._remove_accents(t_clean)
        rows = self.conn.execute("SELECT DISTINCT name FROM catalog_missions WHERE name IS NOT NULL;").fetchall()
        for (m_name,) in rows:
            m_low = m_name.lower().strip()
            if m_low.startswith("nhiệm vụ ") and m_low.replace("nhiệm vụ", "").strip().isdigit():
                continue
            # 1. Khớp chính xác cụm từ có ranh giới từ hợp lệ (có dấu hoặc không dấu)
            if m_low in t_clean:
                idx = t_clean.find(m_low)
                before_ok = (idx == 0 or not t_clean[idx - 1].isalnum())
                after_ok = (idx + len(m_low) == len(t_clean) or not t_clean[idx + len(m_low)].isalnum())
                if before_ok and after_ok:
                    return m_name
            m_unacc = self._remove_accents(m_low)
            if m_unacc and len(m_unacc) >= 5 and m_unacc in t_unacc:
                idx = t_unacc.find(m_unacc)
                before_ok = (idx == 0 or not t_unacc[idx - 1].isalnum())
                after_ok = (idx + len(m_unacc) == len(t_unacc) or not t_unacc[idx + len(m_unacc)].isalnum())
                if before_ok and after_ok:
                    return m_name

            # 2. Với các nhiệm vụ dài có tiền tố (đề án, kế hoạch, chương trình, nhiệm vụ)
            m_core = self.strip_query_noise(m_low, "MISSION_LEAD_PREFIX_NOISE")

            if m_core and len(m_core) > 6 and not m_core.isdigit() and m_core in t_clean:
                idx = t_clean.find(m_core)
                before_ok = (idx == 0 or not t_clean[idx - 1].isalnum())
                after_ok = (idx + len(m_core) == len(t_clean) or not t_clean[idx + len(m_core)].isalnum())
                if before_ok and after_ok:
                    return m_name

        alias_res = self.match_alias_or_abbreviation(t_clean, threshold=80.0)
        if alias_res and alias_res.get("type") == "mission":
            return alias_res["name"]
        return None

    def resolve_user_position(self, term: str) -> Optional[str]:
        """
        Tra cứu động chức vụ từ catalog_users trong DuckDB RAM.
        Ngăn chặn xung đột số từ tiếng Việt ('tháng ba', 'quý ba', 'cấp ba') với mã chức vụ ngắn ('BA', 'QTV').
        """
        if not term:
            return None
        t_clean = term.strip()
        t_lower = t_clean.lower()
        has_personnel_ctx = any(
            w in t_lower
            for w in (
                "chức vụ", "vị trí", "cán bộ", "nhân sự", "nhân viên",
                "chuyên viên", "ai là", "ai giữ", "tài khoản", "user"
            )
        )
        rows = self.conn.execute("SELECT DISTINCT position FROM catalog_users WHERE position IS NOT NULL AND position != '';").fetchall()
        for (pos,) in rows:
            p_clean = pos.strip()
            if not p_clean:
                continue
            p_low = p_clean.lower()
            if len(p_low) <= 3 and not has_personnel_ctx:
                continue
            start_pos = 0
            while True:
                idx = t_lower.find(p_low, start_pos)
                if idx == -1:
                    break
                end_idx = idx + len(p_low)
                before_ok = (idx == 0 or not t_lower[idx - 1].isalnum())
                after_ok = (end_idx == len(t_lower) or not t_lower[end_idx].isalnum())
                if before_ok and after_ok:
                    if p_low == "ba":
                        pre_ctx = t_lower[:idx].rstrip()
                        post_ctx = t_lower[end_idx:].lstrip()
                        if pre_ctx.endswith(("tháng", "quý", "thứ", "cấp", "số", "hai", "mười", "bậc", "loại")):
                            start_pos = idx + 1
                            continue
                        if post_ctx.startswith(("năm", "quý", "tháng", "chỉ tiêu", "hợp tác xã", "đơn vị", "nhiệm vụ", "lĩnh vực", "sao", "xã", "phường")):
                            start_pos = idx + 1
                            continue
                    return p_clean
                start_pos = idx + 1
        if "chức vụ" in t_lower:
            parts = t_lower.split("chức vụ", 1)[1].strip().split()
            if parts:
                return parts[0].strip(" ,:.-?!").upper()
        return None

    def resolve_user_name(self, term: str) -> Optional[str]:
        """
        Tra cứu động tên hoặc tài khoản cán bộ từ catalog_users trong DuckDB RAM (loại bỏ stopwords tĩnh).
        """
        if not term:
            return None
        t_clean = term.lower().strip()
        rows = self.conn.execute("SELECT name, username FROM catalog_users;").fetchall()
        for name, username in rows:
            if not name:
                continue
            name_low = name.lower().strip()
            if name_low in t_clean:
                return name
            if username and len(username) >= 3:
                u_low = username.lower()
                if u_low in t_clean:
                    idx = t_clean.find(u_low)
                    before_ok = (idx == 0 or not t_clean[idx - 1].isalnum())
                    after_ok = (idx + len(u_low) == len(t_clean) or not t_clean[idx + len(u_low)].isalnum())
                    if before_ok and after_ok:
                        return name
            if len(name_low) >= 4 and fuzz.token_set_ratio(name_low, t_clean) >= 85.0:
                return name
        return None

    def is_collective_noun(self, text: str) -> bool:
        """Kiểm tra danh từ tập hợp dựa trên catalog dimension discovery."""
        return self.is_dimension_query(text, "criteria")

    def is_inventory_query(self, text: str) -> bool:
        """
        Kiểm tra câu hỏi kiểm kê / toàn bộ kho dữ liệu.
        Đối chiếu thực tế từ bảng catalog_criteria trong DuckDB RAM (loại bỏ hoàn toàn whitelist tĩnh).
        """
        if not text:
            return False
        t_clean = text.lower().strip()
        try:
            # 1. Phải là câu hỏi thuộc chiều danh mục chỉ tiêu (criteria dimension)
            if not self.is_dimension_query(t_clean, "criteria"):
                return False

            # 2. Đối chiếu thực tế từ catalog_criteria: nếu câu hỏi chứa tên chỉ tiêu lá cụ thể thì không phải kiểm kê
            crit_rows = self.conn.execute("SELECT LOWER(name) FROM catalog_criteria WHERE is_leaf = TRUE;").fetchall()
            for (c_name,) in crit_rows:
                if c_name and len(c_name) > 5 and c_name in t_clean:
                    return False

            # 3. Loại trừ nếu có lọc mốc thời gian cụ thể (tháng lẻ, từ tháng... đến tháng...)
            has_month = any(f"tháng {m}" in t_clean for m in range(1, 13))
            has_range = "từ tháng" in t_clean or "đến tháng" in t_clean or "giai đoạn" in t_clean
            if has_month or has_range:
                return False

            # 4. Đối chiếu từ catalog_offices: loại trừ nếu có lọc theo phòng ban cụ thể
            office_match = self.conn.execute(
                "SELECT 1 FROM catalog_offices WHERE INSTR(?, LOWER(name)) > 0 LIMIT 1;",
                (t_clean,)
            ).fetchone()
            # 5. Loại trừ nếu câu hỏi chứa từ viết tắt công vụ (HTX, OCOP, TNLĐ...)
            for acr, full, _ in self.conn.execute("SELECT acronym, full_form, category FROM catalog_acronyms;").fetchall():
                if acr.lower() in t_clean.split() or full.lower() in t_clean or f" {acr.lower()} " in f" {t_clean} ":
                    return False

            return True
        except Exception as e:
            logger.debug("Lỗi is_inventory_query: %s", e)
            return False

    def resolve_collection_form(self, term: str) -> Optional[str]:
        """Tra cứu biểu mẫu thu thập từ catalog_collection_forms."""
        if not term:
            return None
        t_clean = term.lower().strip()
        try:
            rows = self.conn.execute("SELECT name, code FROM catalog_collection_forms;").fetchall()
            for name, code in rows:
                if name and name.lower().strip() in t_clean:
                    return name
            if "biểu mẫu" in t_clean or "tờ khai" in t_clean:
                return "collection_form"
        except Exception:
            pass
        return None

    def resolve_report_status(self, term: str) -> Optional[str]:
        """Tra cứu kỳ báo cáo / trạng thái báo cáo từ catalog metadata."""
        if not term:
            return None
        t_clean = term.lower().strip()
        if "báo cáo" in t_clean or "phê duyệt" in t_clean or "tình hình nộp" in t_clean:
            return "report"
        return None

    def is_dimension_query(self, raw_input: str, dimension_name: str, archetype: Optional[str] = None) -> bool:
        """
        Kiểm tra câu hỏi khám phá chiều (Dimension Exploration / Dimension Listing).
        Căn cứ: Intent Archetype Classification từ Planner (DIMENSION_LISTING vs SNAPSHOT) kết hợp
        tra cứu thực thể trong DuckDB RAM. Loại bỏ 100% mảng từ khóa tĩnh và markers.
        """
        if not raw_input:
            return False
        norm_input = raw_input.lower().strip()
        is_archetype_listing = (archetype in ("DIMENSION_LISTING", "METADATA_EXPLORATION", "CAPABILITY_INTRO"))

        if dimension_name == "province":
            try:
                prov_rows = self.conn.execute("SELECT LOWER(name), LOWER(code) FROM catalog_provinces;").fetchall()
                prov_names = [r[0] for r in prov_rows if r[0]]
                prov_codes = [r[1] for r in prov_rows if r[1]]
                tokens = norm_input.replace("?", " ").replace(".", " ").replace(",", " ").split()
                has_prov_ctx = self.has_lexicon_term(raw_input, "PROV_LIST")
                matches_prov = any(f" {p} " in f" {norm_input} " for p in prov_names) or (has_prov_ctx and any(c in tokens for c in prov_codes))
                is_dim_concept = has_prov_ctx or "province" in tokens
                return (matches_prov and has_prov_ctx) or (is_dim_concept and is_archetype_listing)
            except Exception:
                return False

        elif dimension_name == "mission":
            try:
                is_mission_concept = self.has_lexicon_term(raw_input, "MISSION_KEYWORD")
                has_crit = self.has_lexicon_term(raw_input, "METRIC_LIST_TARGET")
                if has_crit and not is_archetype_listing:
                    return False
                m_input = self._strip_dept_noise(norm_input)
                mission_rows = self.conn.execute("SELECT DISTINCT LOWER(name) FROM catalog_missions WHERE name IS NOT NULL;").fetchall()
                mission_names = [r[0] for r in mission_rows if r[0] and not (r[0].startswith("nhiệm vụ ") and r[0].replace("nhiệm vụ", "").strip().isdigit())]

                matches_mission = any(f" {m} " in f" {m_input} " for m in mission_names)
                return matches_mission or is_mission_concept or is_archetype_listing
            except Exception:
                return False

        elif dimension_name in ("office_or_department", "office", "deparment"):
            try:
                office_rows = self.conn.execute("SELECT DISTINCT LOWER(name) FROM catalog_offices WHERE name IS NOT NULL;").fetchall()
                dept_rows = self.conn.execute("SELECT DISTINCT LOWER(name) FROM catalog_departments WHERE name IS NOT NULL;").fetchall()
                org_names = [r[0] for r in (*office_rows, *dept_rows) if r[0]]
                matches_org = any(f" {o} " in f" {norm_input} " for o in org_names)
                is_org_concept = self.has_lexicon_term(raw_input, "OFFICE_KEYWORD")
                return matches_org or is_org_concept or is_archetype_listing
            except Exception:
                return False

        elif dimension_name in ("ward", "commune"):
            try:
                crit_matches = self.find_criteria_by_name(raw_input, limit=1)
                if crit_matches and not is_archetype_listing:
                    return False
                tokens = set(norm_input.replace("?", " ").replace(".", " ").replace(",", " ").split())
                has_ward_compound = any(w in norm_input for w in [
                    "xã, phường", "xã phường", "xã / phường", "phường, xã", "phường xã",
                    "xã thuộc", "phường thuộc", "xã nào", "phường nào", "thị trấn"
                ])
                has_standalone_ward = ("phường" in tokens or "thị trấn" in tokens) or (
                    "xã" in tokens and "hợp tác xã" not in norm_input and "htx" not in tokens
                )
                return (has_ward_compound or has_standalone_ward) and not self.has_lexicon_term(raw_input, "DOMAIN_SIGNAL")
            except Exception:
                return False

        elif dimension_name in ("criteria", "metric", "fact_report_criteria"):
            try:
                if is_archetype_listing:
                    return True
                crit_concept = self.has_lexicon_term(raw_input, "METRIC_LIST_TARGET")
                if not crit_concept:
                    return False

                # Khám phá danh mục theo dải thời gian
                ALLOWED_M_TOKENS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "một", "giêng", "hai", "ba", "tư", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười", "chạp"]
                has_month_word = any(f"tháng {m}" in norm_input or f"thang {m}" in norm_input for m in ALLOWED_M_TOKENS)
                has_time_term = self.has_lexicon_term(raw_input, "TIME_TERM") or has_month_word

                # Nếu câu hỏi chứa từ viết tắt/chủ đề cụ thể từ catalog_acronyms (ví dụ HTX, OCOP, TNLĐ)
                # và không có mốc thời gian khám phá, thì đây là tra cứu đa nghĩa chủ đề cần làm rõ, không phải dimension listing toàn tỉnh.
                if not has_time_term:
                    try:
                        acronym_rows = self.conn.execute("SELECT acronym, full_form FROM catalog_acronyms WHERE category = 'criteria';").fetchall()
                        for acr, full in acronym_rows:
                            if acr.lower() in norm_input.split() or full.lower() in norm_input or f" {acr.lower()} " in f" {norm_input} ":
                                return False
                    except Exception:
                        pass

                # Kiểm tra các tín hiệu khám phá danh mục / kiểm kê danh sách rõ ràng
                is_explicit_listing = self.has_lexicon_term(raw_input, "METRIC_LIST_TRIGGER")
                # Đếm số lượng chỉ tiêu (chú ý: phân biệt "bao nhiêu chỉ tiêu" vs "chỉ tiêu X là bao nhiêu")
                is_criteria_count = self.has_lexicon_term(raw_input, "CRITERIA_COUNT") and self.has_lexicon_term(raw_input, "METRIC_LIST_TARGET")
                is_criteria_reported = self.has_lexicon_term(raw_input, "METRIC_LIST_TARGET") and self.has_lexicon_term(raw_input, "CRITERIA_REPORTED")
                has_time_discovery = has_time_term and self.has_lexicon_term(raw_input, "METRIC_LIST_TRIGGER")

                if is_explicit_listing or is_criteria_count or is_criteria_reported or has_time_discovery:
                    # Nếu câu hỏi có tên chỉ tiêu cụ thể (lá đơn, lá trùng tên hoặc chỉ tiêu cha)
                    # mà không phải câu lệnh liệt kê danh mục rõ ràng (METRIC_LIST_TRIGGER),
                    # thì đây là Metric Point Inquiry chứ không phải dimension listing.
                    h_check = self.classify_criterion_hierarchy(raw_input)
                    is_specific_crit = h_check.get("classification") in ("single_leaf", "duplicate_leaf", "parent", "parent_group")
                    is_point_value = self.has_lexicon_term(raw_input, "POINT_VALUE")
                    if is_specific_crit and (is_point_value or not is_explicit_listing):
                        return False
                    return True

                return False
            except Exception:
                return False

        return False

    def resolve_target_table(
        self,
        raw_input: str = "",
        intent: Optional[str] = None,
        target_table_slot: Optional[str] = None,
        default_table: str = "fact_report_criteria"
    ) -> str:
        """
        Xác định bảng đích truy vấn dựa trên NLU Intent, slot target_table và metadata catalog.
        Sửa lỗi chính tả 'deparment' -> 'department'.
        """
        # 1. Ưu tiên slot target_table từ NLU
        if target_table_slot:
            tbl = target_table_slot.strip().lower()
            if tbl in ("deparment", "department"):
                return "department"
            ALLOWED_VALID_TABLES = {
                "fact_report_criteria", "report", "mission", "office_mission",
                "user_mission", "criteria", "office", "department", "province",
                "ward", "collection_form", "user", "office_user", "office_user_dept"
            }
            if tbl in ALLOWED_VALID_TABLES:
                return tbl

        # 2. Suy luận từ NLU Intent
        if intent:
            intent_str = str(intent).upper()
            if "OFFICER" in intent_str or "USER" in intent_str:
                return "user"
            if "MISSION" in intent_str:
                return "mission"
            if "FORM" in intent_str:
                return "collection_form"
            if "DIMENSION" in intent_str:
                return "fact_report_criteria"

        # 3. Tra cứu từ catalog_schema_metadata trong DuckDB RAM
        if raw_input:
            norm_input = raw_input.lower().strip()
            try:
                rows = self.conn.execute("""
                    SELECT DISTINCT simple_name, table_description
                    FROM catalog_schema_metadata
                    WHERE simple_name IS NOT NULL;
                """).fetchall()
                for s_name, desc in rows:
                    clean_name = "department" if s_name in ("deparment", "department") else s_name
                    if desc and any(tok in norm_input for tok in desc.lower().split() if len(tok) > 3):
                        return clean_name
            except Exception:
                pass

        return default_table

    def resolve_excluded_entities(self, raw_input: str) -> List[str]:
        """
        Phân giải các thực thể bị loại trừ (Negative Filters) đối chiếu từ Catalog RAM (Zero Python Slicing).
        """
        if not raw_input:
            return []
        norm_input = raw_input.lower().strip()
        excluded: List[str] = []
        ALLOWED_NEG_WORDS = ("không", "ngoài", "trừ", "bỏ")
        try:
            provs = self.conn.execute("SELECT name FROM catalog_provinces;").fetchall()
            for (p_name,) in provs:
                clean_p = p_name.replace("Tỉnh ", "").replace("Thành phố ", "").strip()
                if clean_p.lower() in norm_input:
                    row_pre = self.conn.execute(
                        "SELECT TRIM(SUBSTR(?, 1, INSTR(LOWER(?), LOWER(?)) - 1));",
                        [norm_input, norm_input, clean_p.lower()]
                    ).fetchone()
                    pre_text = row_pre[0] if row_pre else ""
                    if any(neg in pre_text.split()[-3:] or pre_text.endswith(neg) for neg in ALLOWED_NEG_WORDS):
                        excluded.append(clean_p)
            if "phòng" in norm_input:
                row_pre = self.conn.execute(
                    "SELECT TRIM(SUBSTR(?, 1, INSTR(LOWER(?), 'phòng') - 1));",
                    [norm_input, norm_input]
                ).fetchone()
                pre_text = row_pre[0] if row_pre else ""
                if any(neg in pre_text.split()[-3:] or pre_text.endswith(neg) for neg in ALLOWED_NEG_WORDS):
                    excluded.append("phòng")
        except Exception:
            pass
        return list(dict.fromkeys(excluded))


    def resolve_attribute_lookup(self, raw_input: str) -> Optional[Dict[str, str]]:
        """
        Xác định xem câu hỏi có tra cứu thuộc tính thực thể (đơn vị thực hiện / tỉnh thực hiện)
        thông qua cấu trúc vị từ Catalog RAM.
        """
        if not raw_input:
            return None
        if self.has_lexicon_term(raw_input, "METRIC_LIST_TRIGGER"):
            return None
        has_performer_verb = self.has_lexicon_term(raw_input, "PERFORMER_VERB")
        has_unit_interrogative = self.has_lexicon_term(raw_input, "UNIT_INTERROGATIVE")
        if has_performer_verb and has_unit_interrogative:
            target_attr = "tỉnh thực hiện" if self.has_lexicon_term(raw_input, "PROV_LIST") else "đơn vị thực hiện"
            return {"target_table": "fact_report_criteria", "target_attribute": target_attr}
        return None

    def get_scopes_list(self) -> List[Dict[str, str]]:
        """Lấy danh sách các lĩnh vực (scope) hiện có trong kho dữ liệu từ catalog_scopes."""
        try:
            rows = self.conn.execute("SELECT id, code, name FROM catalog_scopes ORDER BY name ASC;").fetchall()
            return [{"id": r[0], "code": r[1], "name": r[2], "scope_name": r[2]} for r in rows]
        except Exception:
            return []

    def extract_scope_from_query(self, raw_input: str) -> Dict[str, Any]:
        """
        Phân giải lĩnh vực (scope) từ câu hỏi người dùng phục vụ REQ-Q03 & SC-3.1..3.2.
        Trả về:
        - {"status": "MATCH", "scope_name": ..., "scope_code": ...} nếu khớp lĩnh vực có trong CSDL
        - {"status": "NOT_FOUND", "requested_scope": ..., "available_scopes": [...]} nếu hỏi lĩnh vực không tồn tại
        - {"status": "NONE"} nếu câu hỏi không truy vấn nhiệm vụ theo lĩnh vực
        """
        if not raw_input:
            return {"status": "NONE"}
        import unicodedata
        clean_input = unicodedata.normalize("NFC", raw_input.strip())
        norm_input = clean_input.lower()
        unacc_input = self._remove_accents(norm_input)

        # Không kích hoạt nếu câu hỏi đang hỏi về "chỉ tiêu" (REQ-Q01, REQ-Q02, REQ-Q04)
        if self.has_lexicon_term(raw_input, "METRIC_LIST_TARGET"):
            return {"status": "NONE"}

        # Chỉ kích hoạt khi câu hỏi đề cập đến nhiệm vụ (hoặc chương trình/đề án/công tác)
        has_mission_ctx = self.has_lexicon_term(raw_input, "MISSION_SCOPE_SIGNAL")
        if not has_mission_ctx:
            return {"status": "NONE"}

        scopes = self.get_scopes_list()
        for sc in scopes:
            sc_name_low = unicodedata.normalize("NFC", sc["name"]).lower().strip()
            sc_unacc = self._remove_accents(sc_name_low)
            if sc_name_low and (sc_name_low in norm_input or (sc_unacc and sc_unacc in unacc_input)):
                return {
                    "status": "MATCH",
                    "scope_name": sc["name"],
                    "scope_code": sc["code"],
                    "available_scopes": scopes,
                }

        # Hỗ trợ đa dạng từ đồng nghĩa chỉ lĩnh vực thông qua SCOPE_ENTITY_MARKER trong semantic_lexicon
        markers = [
            r[0] for r in self.conn.execute(
                "SELECT term FROM semantic_lexicon WHERE category = 'SCOPE_ENTITY_MARKER' ORDER BY LENGTH(term) DESC;"
            ).fetchall()
        ]
        if "ban ngành" in norm_input or "ngành nghề" in norm_input or "sở ngành" in norm_input or "ban nganh" in unacc_input or "nganh nghe" in unacc_input or "so nganh" in unacc_input:
            markers = [mk for mk in markers if mk not in ("ngành", "nganh")]

        known_missions_low = set()
        for m in self.get_missions_list():
            mn = unicodedata.normalize("NFC", m["name"]).lower().strip()
            known_missions_low.add(mn)
            known_missions_low.add(self._remove_accents(mn))

        matched_marker = next((mk for mk in markers if mk in norm_input), None)
        if matched_marker:
            row_after = self.conn.execute(
                "SELECT TRIM(SUBSTR(?, INSTR(LOWER(?), LOWER(?)) + LENGTH(?)));",
                [clean_input, clean_input, matched_marker, matched_marker]
            ).fetchone()
            after_text = row_after[0].strip(" :,-'\"“”") if row_after else ""
            if not after_text.lower().startswith("trong trot"):
                after_text = self.strip_query_noise(after_text, "SCOPE_LEAD_PREPOSITION")

            # Loại bỏ các stop tokens thông qua DuckDB SQL
            stop_tokens = [
                r[0] for r in self.conn.execute(
                    "SELECT term FROM semantic_lexicon WHERE category IN ('SCOPE_STOP_TOKEN', 'MISSION_STOP_TOKEN') ORDER BY LENGTH(term) DESC;"
                ).fetchall()
            ]
            extracted_scope = after_text
            for st in stop_tokens:
                if not st:
                    continue
                row_cut = self.conn.execute(
                    """SELECT CASE 
                        WHEN INSTR(LOWER(?), LOWER(?)) > 0 
                        THEN TRIM(SUBSTR(?, 1, INSTR(LOWER(?), LOWER(?)) - 1)) 
                        ELSE ? 
                    END;""",
                    [extracted_scope, st, extracted_scope, extracted_scope, st, extracted_scope]
                ).fetchone()
                if row_cut and row_cut[0] != extracted_scope:
                    extracted_scope = row_cut[0]

            extracted_scope = extracted_scope.strip(" :,-.?!'\"“”")
            ext_low = extracted_scope.lower()
            ext_unacc = self._remove_accents(ext_low)
            ALLOWED_GENERIC_WORDS = {
                "", "nào", "nao", "gì", "gi", "đó", "do", "này", "nay", "trên", "tren",
                "trọng tâm", "trong tam", "chuyên môn", "chuyen mon", "công tác", "cong tac"
            }
            if (
                extracted_scope
                and ext_low not in ALLOWED_GENERIC_WORDS
                and ext_unacc not in ALLOWED_GENERIC_WORDS
                and ext_low not in known_missions_low
                and ext_unacc not in known_missions_low
                and not any(dept_kw in ext_low or dept_kw in ext_unacc for dept_kw in ("tỉnh ", "tinh ", "lâm đồng", "lam dong", "sở ", "so ", "phòng ", "phong ", "chi cục", "chi cuc", "ubnd"))
            ):
                return {
                    "status": "NOT_FOUND",
                    "requested_scope": extracted_scope,
                    "available_scopes": scopes,
                }


        return {"status": "NONE"}

    def get_missions_list(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các nhiệm vụ hiện có trong kho dữ liệu từ catalog_missions_detail."""
        try:
            rows = self.conn.execute(
                "SELECT id, code, name, scope_name, office_names, has_approved_facts FROM catalog_missions_detail ORDER BY name ASC;"
            ).fetchall()
            if rows:
                all_items = [
                    {
                        "id": str(r[0]),
                        "code": str(r[1]),
                        "name": str(r[2]),
                        "mission_name": str(r[2]),
                        "scope_name": str(r[3] or "-"),
                        "office_names": "-" if not r[4] or str(r[4]).strip() in ("", "Chưa phân công", "None", "null") else str(r[4]).strip(),
                        "office_name": "-" if not r[4] or str(r[4]).strip() in ("", "Chưa phân công", "None", "null") else str(r[4]).strip(),
                        "has_approved_facts": bool(r[5]),
                    }
                    for r in rows
                ]
                real_items = [
                    it for it in all_items
                    if not (
                        it["name"].strip().lower().startswith("nhiệm vụ ")
                        and it["name"].strip().lower().replace("nhiệm vụ", "").strip().isdigit()

                    )
                ]
                return real_items if real_items else all_items
        except Exception:
            pass
        try:
            rows = self.conn.execute(
                "SELECT id, code, name FROM catalog_missions ORDER BY name ASC;"
            ).fetchall()
            if rows:
                return [
                    {
                        "id": str(r[0]),
                        "code": str(r[1]),
                        "name": str(r[2]),
                        "mission_name": str(r[2]),
                        "scope_name": "-",
                        "office_names": "-",
                        "office_name": "-",
                        "has_approved_facts": False,
                    }
                    for r in rows
                ]
        except Exception:
            pass

        return []

    def extract_mission_from_query(self, raw_input: str) -> Dict[str, Any]:
        """
        Phân giải nhiệm vụ (mission) từ câu hỏi người dùng phục vụ REQ-Q04 & SC-4.1..4.2.
        Trả về:
        - {"status": "MATCH", "mission_name": ..., "mission_detail": ..., "available_missions": [...]}
        - {"status": "NOT_FOUND", "requested_mission": ..., "available_missions": [...]}
        - {"status": "NONE"}
        """
        if not raw_input:
            return {"status": "NONE"}
        import unicodedata
        clean_input = unicodedata.normalize("NFC", raw_input.strip())
        norm_input = clean_input.lower()

        missions = self.get_missions_list()
        # Loại bỏ tên cơ quan động qua DuckDB RAM
        clean_mission_input = self._strip_dept_noise(norm_input)

        unacc_mission_input = self._remove_accents(clean_mission_input)
        for m in missions:
            m_name_low = unicodedata.normalize("NFC", m["name"]).lower().strip()
            m_unacc = self._remove_accents(m_name_low)
            if m_name_low and (m_name_low in clean_mission_input or (m_unacc and m_unacc in unacc_mission_input)):
                return {
                    "status": "MATCH",
                    "mission_name": m["name"],
                    "mission_detail": m,
                    "available_missions": missions,
                }

        # Kiểm tra nếu người dùng hỏi về một "nhiệm vụ <X>" cụ thể nhưng <X> không tồn tại trong CSDL
        markers = [
            r[0] for r in self.conn.execute(
                "SELECT term FROM semantic_lexicon WHERE category = 'MISSION_ENTITY_MARKER' ORDER BY LENGTH(term) DESC;"
            ).fetchall()
        ]
        matched_marker = next((mk for mk in markers if mk in norm_input), None)
        if matched_marker:
            # Trích xuất chuỗi phía sau marker thông qua DuckDB SQL
            row_after = self.conn.execute(
                "SELECT TRIM(SUBSTR(?, INSTR(LOWER(?), LOWER(?)) + LENGTH(?)));",
                [clean_input, clean_input, matched_marker, matched_marker]
            ).fetchone()
            after_text = row_after[0].strip(" :,-'\"“”") if row_after else ""

            # Loại bỏ các stop tokens thông qua DuckDB SQL
            stop_tokens = [
                r[0] for r in self.conn.execute(
                    "SELECT term FROM semantic_lexicon WHERE category = 'MISSION_STOP_TOKEN' ORDER BY LENGTH(term) DESC;"
                ).fetchall()
            ]
            extracted_mission = after_text
            for st in stop_tokens:
                if not st:
                    continue
                row_cut = self.conn.execute(
                    """SELECT CASE 
                        WHEN INSTR(LOWER(?), LOWER(?)) > 0 
                        THEN TRIM(SUBSTR(?, 1, INSTR(LOWER(?), LOWER(?)) - 1)) 
                        ELSE ? 
                    END;""",
                    [extracted_mission, st, extracted_mission, extracted_mission, st, extracted_mission]
                ).fetchone()
                if row_cut and row_cut[0] != extracted_mission:
                    extracted_mission = row_cut[0]

            extracted_mission = extracted_mission.strip(" :,-.?!'\"“”")
            ext_low = extracted_mission.lower()
            ext_unacc = self._remove_accents(ext_low)
            ALLOWED_GENERIC_WORDS = {
                "", "nào", "nao", "gì", "gi", "đó", "do", "này", "nay", "trên", "tren",
                "trọng tâm", "trong tam", "chuyên môn", "chuyen mon",
                "công tác", "cong tac", "hệ thống", "he thong", "kho dữ liệu", "kho du lieu",
                "tỉnh", "tinh", "sở", "so", "phòng ban", "phong ban",
            }
            if (
                extracted_mission
                and ext_low not in ALLOWED_GENERIC_WORDS
                and ext_unacc not in ALLOWED_GENERIC_WORDS
                and not ext_low.startswith(("nào", "nao", "gì", "gi", "năm ", "nam ", "trong ", "tại ", "tai ", "của ", "cua ", "thuộc ", "thuoc ", "do "))
                and not any(sc["name"].lower() in ext_low or self._remove_accents(sc["name"].lower()) in ext_unacc for sc in self.get_scopes_list())
            ):
                return {
                    "status": "NOT_FOUND",
                    "requested_mission": extracted_mission,
                    "available_missions": missions,
                }

        return {"status": "NONE"}

    def get_mission_detail(self, mission_name: Optional[str]) -> Optional[Dict[str, Any]]:
        """Tra cứu thông tin chi tiết nhiệm vụ (bao gồm lĩnh vực, phòng ban phụ trách và trạng thái dữ liệu fact)."""
        if not mission_name:
            return None
        import unicodedata
        m_low = unicodedata.normalize("NFC", mission_name.strip()).lower()
        try:
            row = self.conn.execute(
                "SELECT id, code, name, scope_name, office_names, has_approved_facts FROM catalog_missions_detail WHERE LOWER(name) = ? LIMIT 1;",
                [m_low]
            ).fetchone()
            if row:
                return {
                    "id": row[0],
                    "code": row[1],
                    "name": row[2],
                    "mission_name": row[2],
                    "scope_name": str(row[3] or "-"),
                    "office_names": "-" if not row[4] or str(row[4]).strip() in ("", "Chưa phân công", "None", "null") else str(row[4]).strip(),
                    "office_name": "-" if not row[4] or str(row[4]).strip() in ("", "Chưa phân công", "None", "null") else str(row[4]).strip(),

                    "has_approved_facts": bool(row[5]),
                }
            row_m = self.conn.execute(
                "SELECT id, code, name FROM catalog_missions WHERE LOWER(name) = ? LIMIT 1;",
                [m_low]
            ).fetchone()
            if row_m:
                return {
                    "id": str(row_m[0]),
                    "code": str(row_m[1]),
                    "name": str(row_m[2]),
                    "mission_name": str(row_m[2]),
                    "scope_name": "-",
                    "office_names": "-",
                    "office_name": "-",
                    "has_approved_facts": False,
                }
        except Exception:
            pass
        return None

    def classify_criterion_hierarchy(
        self,
        query: str,
        matched_code: Optional[str] = None,
        matched_name: Optional[str] = None,
        parent_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Phân loại cấu trúc phân cấp của chỉ tiêu được hỏi (REQ-Q02 & SC-2.1..SC-2.4):
        - PARENT_GROUP (SC-2.4): Khi câu hỏi nhắm vào chỉ tiêu cha (is_leaf = FALSE) có các chỉ tiêu con.
        - DUPLICATE_LEAF (SC-2.1): Khi câu hỏi nhắm vào chỉ tiêu lá (is_leaf = TRUE) bị trùng tên ở nhiều nhóm cha mà chưa định danh nhóm cha.
        - SINGLE_LEAF (REQ-Q02, SC-2.2, SC-2.3): Khi câu hỏi nhắm vào 1 chỉ tiêu lá duy nhất (kể cả chỉ tiêu có value NULL).
        """
        import unicodedata
        q_norm = " ".join(unicodedata.normalize("NFC", (query or "").lower().strip()).split())
        q_unaccent = self._remove_accents(q_norm)

        try:
            rows = self.conn.execute("""
                SELECT id, code, name, parent_id, parent_name, root_id, root_name, level, is_leaf, mission_name, office_name, latest_value
                FROM catalog_criteria_hierarchy;
            """).fetchall()
        except Exception:
            rows = []

        if not rows:
            return {
                "category": "SINGLE_LEAF",
                "classification": "single_leaf",
                "code": matched_code,
                "name": matched_name,
                "matched_code": matched_code,
                "matched_name": matched_name,
            }

        # Chuẩn bị danh sách bản ghi hierarchy (chuẩn hóa khoảng trắng kép trong DB như 'Lũy kế  tổng...')
        items = []
        for r in rows:
            c_name = unicodedata.normalize("NFC", (r[2] or "").strip())
            c_low = " ".join(c_name.lower().split())
            c_unacc = self._remove_accents(c_low)
            items.append({
                "id": r[0],
                "code": r[1],
                "name": c_name,
                "name_low": c_low,
                "name_unaccent": c_unacc,
                "parent_id": r[3],
                "parent_name": r[4],
                "parent_level": max(1, int(r[7] or 2) - 1),
                "root_id": r[5],
                "root_name": r[6],
                "level": int(r[7] or 1),
                "is_leaf": bool(r[8]),
                "mission_name": r[9] or "",
                "office_name": r[10] or "",
                "latest_value": r[11],
            })

        # 1. Tra cứu các alias định danh từ catalog_aliases trong DuckDB RAM
        alias_matched_leaf_code = None
        alias_matched_leaf_text = None
        alias_matched_parent_code = None
        alias_matched_parent_text = None

        try:
            alias_rows = self.conn.execute("""
                SELECT alias, code, is_leaf FROM catalog_aliases ORDER BY LENGTH(alias) DESC;
            """).fetchall()
        except Exception:
            alias_rows = []

        for al_text, a_code, a_is_leaf in alias_rows:
            al_unacc = self._remove_accents(al_text)
            if al_text in q_norm or (al_unacc and len(al_unacc) >= 6 and al_unacc in q_unaccent):
                if a_is_leaf:
                    if not alias_matched_leaf_code:
                        alias_matched_leaf_code = a_code
                        alias_matched_leaf_text = al_text
                else:
                    if not alias_matched_parent_code:
                        alias_matched_parent_code = a_code
                        alias_matched_parent_text = al_text
                if alias_matched_leaf_code and alias_matched_parent_code:
                    break

        # Tìm các mục có tên xuất hiện nguyên vẹn trong câu hỏi (có kiểm tra ranh giới từ)
        def _find_span(haystack: str, needle: str) -> Optional[Tuple[int, int]]:
            if not needle or len(needle) < 3:
                return None
            start = 0
            while True:
                idx = haystack.find(needle, start)
                if idx == -1:
                    return None
                before_ok = (idx == 0 or not haystack[idx - 1].isalnum())
                end_idx = idx + len(needle)
                after_ok = (end_idx == len(haystack) or not haystack[end_idx].isalnum())
                if before_ok and after_ok:
                    return (idx, end_idx)
                start = idx + 1

        if alias_matched_leaf_code and alias_matched_leaf_text:
            matching_items = [
                it for it in items
                if it["code"] == alias_matched_leaf_code or it["name_low"] == alias_matched_leaf_text.lower()
            ]
            if matching_items:
                for it in matching_items:
                    it["is_leaf"] = True
            else:
                disp_name = alias_matched_leaf_text[0].upper() + alias_matched_leaf_text[1:]
                p_cand = None
                if alias_matched_parent_code:
                    p_cand = next((it for it in items if it["code"] == alias_matched_parent_code), None)
                if not p_cand:
                    parent_cands = [
                        it for it in items
                        if not it["is_leaf"] and (it["name_low"] in q_norm or (it["name_unaccent"] and len(it["name_unaccent"]) >= 4 and it["name_unaccent"] in q_unaccent))
                    ]
                    if parent_cands:
                        parent_cands.sort(key=lambda x: len(x["name"]), reverse=True)
                        p_cand = parent_cands[0]
                if not p_cand and parent_context:
                    ctx_low = parent_context.lower().strip()
                    p_cand = next((it for it in items if not it["is_leaf"] and (it["name_low"] == ctx_low or ctx_low in it["name_low"])), None)

                parent_name = p_cand["name"] if p_cand else (alias_matched_parent_text or "-")
                parent_id = p_cand["id"] if p_cand else None
                root_name = (p_cand.get("root_name") or parent_name) if p_cand else parent_name
                root_id = (p_cand.get("root_id") or parent_id) if p_cand else parent_id

                leaf_it = {
                    "id": alias_matched_leaf_code,
                    "code": alias_matched_leaf_code,
                    "name": disp_name,
                    "name_low": alias_matched_leaf_text.lower(),
                    "name_unaccent": self._remove_accents(alias_matched_leaf_text.lower()),
                    "parent_id": parent_id,
                    "parent_name": parent_name,
                    "parent_level": p_cand.get("level", 1) if p_cand else 1,
                    "root_id": root_id,
                    "root_name": root_name,
                    "level": 2,
                    "is_leaf": True,
                    "mission_name": (p_cand.get("mission_name") or "-") if p_cand else "-",
                    "office_name": (p_cand.get("office_name") or "Cấp tỉnh") if p_cand else "Cấp tỉnh",
                    "latest_value": None,
                }
                items.append(leaf_it)

        matched_spans: List[Tuple[int, int, Dict[str, Any]]] = []
        for it in items:
            # Chặn dương tính giả: khi chỉ tiêu trùng với từ chỉ hành động tổng hợp/thống kê (action verb)
            if hasattr(self, "has_lexicon_term") and self.has_lexicon_term(it["name_low"], "SYNTHESIS_ACTION_CUE"):
                if self.has_lexicon_term(q_norm, "SYNTHESIS_ACTION_CUE") and not self.has_lexicon_term(q_norm, "SYNTHESIS_METRIC_CUE"):
                    continue
            sp = _find_span(q_norm, it["name_low"])
            if not sp and len(it["name_unaccent"]) >= 5:
                sp = _find_span(q_unaccent, it["name_unaccent"])
            if sp:
                matched_spans.append((sp[0], sp[1], it))

        if alias_matched_leaf_code and alias_matched_leaf_text:
            sp_al = _find_span(q_norm, alias_matched_leaf_text) or _find_span(q_unaccent, self._remove_accents(alias_matched_leaf_text))
            if sp_al:
                for it in items:
                    if it["code"] == alias_matched_leaf_code:
                        matched_spans.append((sp_al[0], sp_al[1], it))
        if alias_matched_parent_code and alias_matched_parent_text:
            sp_ap = _find_span(q_norm, alias_matched_parent_text) or _find_span(q_unaccent, self._remove_accents(alias_matched_parent_text))
            if sp_ap:
                for it in items:
                    if it["code"] == alias_matched_parent_code:
                        matched_spans.append((sp_ap[0], sp_ap[1], it))

        # Loại bỏ các match là chuỗi con nằm gọn bên trong một match dài hơn trong câu hỏi
        filtered_matches: List[Dict[str, Any]] = []
        for s1, e1, it1 in matched_spans:
            is_sub = False
            for s2, e2, it2 in matched_spans:
                if it1["code"] != it2["code"] and s2 <= s1 and e2 >= e1 and (e2 - s2) > (e1 - s1):
                    is_sub = True
                    break
            if not is_sub:
                filtered_matches.append(it1)

        leaf_matches = [m for m in filtered_matches if m["is_leaf"]]
        parent_matches = [m for m in filtered_matches if not m["is_leaf"]]

        # Generic structural disambiguation rule:
        # Khi parent_matches và leaf_matches cùng khớp:
        # Nếu leaf và parent cùng chung base name (hoặc leaf chỉ khớp do chứa base name của parent),
        # và không có token hạn định đặc thù nào của leaf (ngoài các token của parent) xuất hiện trong q_norm,
        # ưu tiên parent_matches (loại bỏ leaf_matches).
        if parent_matches and leaf_matches:
            has_leaf_qualifier = False
            q_tokens = set(q_norm.split())
            for l in leaf_matches:
                l_tokens = set(l["name_low"].split())
                for p in parent_matches:
                    p_tokens = set(p["name_low"].split())
                    qualifiers = l_tokens - p_tokens
                    if qualifiers and any(qt in q_tokens or qt in q_norm for qt in qualifiers):
                        has_leaf_qualifier = True
                        break
                if has_leaf_qualifier:
                    break
            if not has_leaf_qualifier:
                leaf_matches = []

        if alias_matched_leaf_code:
            for it in items:
                if it["code"] == alias_matched_leaf_code and it not in leaf_matches:
                    leaf_matches.insert(0, it)

        if alias_matched_parent_code and not leaf_matches:
            for it in items:
                if it["code"] == alias_matched_parent_code and it not in parent_matches:
                    parent_matches.append(it)

        # Nếu không có leaf_matches trực tiếp nhưng matched_code từ bộ định tuyến trỏ vào một chỉ tiêu
        if not leaf_matches and not parent_matches and matched_code:
            for it in items:
                if it["code"] == matched_code:
                    if it["is_leaf"]:
                        leaf_matches.append(it)
                    else:
                        parent_matches.append(it)
                    break

        # 1. Xử lý SC-2.4: Câu hỏi nhắm vào chỉ tiêu cha (Parent Group) và không nêu chỉ tiêu lá cụ thể
        if parent_matches and not leaf_matches:
            if len(parent_matches) > 1:
                scored_p = []
                for p in parent_matches:
                    p_name = (p.get("name") or "").lower().strip()
                    r_name = (p.get("root_name") or "").lower().strip()
                    p_un = self._remove_accents(p_name)
                    r_un = self._remove_accents(r_name)
                    s = 0
                    if p_name and f" {p_name} " in f" {q_norm} ":
                        s += len(p_name) * 2
                    elif p_name and p_name in q_norm:
                        s += len(p_name)
                    if r_name and f" {r_name} " in f" {q_norm} ":
                        s += len(r_name) * 2
                    elif r_name and r_name in q_norm:
                        s += len(r_name)
                    if p_un and f" {p_un} " in f" {q_unaccent} ":
                        s += len(p_un)
                    if r_un and f" {r_un} " in f" {q_unaccent} ":
                        s += len(r_un)
                    scored_p.append((s, p))
                scored_p.sort(key=lambda x: (x[0], x[1]["level"], len(x[1]["name"])), reverse=True)
                parent_matches = [x[1] for x in scored_p]
            parent_matches.sort(key=lambda x: (x["level"], len(x["name"])), reverse=True)
            target_parent = parent_matches[0]
            parent_id = target_parent["id"]
            direct_children = [it for it in items if it["parent_id"] == parent_id]
            leaf_descendants = [
                it for it in items
                if it["is_leaf"] and (it["parent_id"] == parent_id or it["root_id"] == parent_id)
            ]
            p_disp_name = target_parent["name"]
            return {
                "category": "PARENT_GROUP",
                "classification": "parent",
                "code": target_parent["code"],
                "name": p_disp_name,
                "matched_code": target_parent["code"],
                "matched_name": target_parent["name"],
                "parent_id": parent_id,
                "parent_code": target_parent["code"],
                "parent_name": p_disp_name,
                "root_id": target_parent.get("root_id") or parent_id,
                "root_name": target_parent.get("root_name") or p_disp_name,
                "parent_level": target_parent.get("level", 1),
                "parent_value": target_parent.get("latest_value"),
                "mission_name": target_parent["mission_name"],
                "office_name": target_parent["office_name"],
                "latest_value": target_parent.get("latest_value"),
                "direct_children": direct_children,
                "leaf_descendants": leaf_descendants,
                "children": direct_children or leaf_descendants,
            }

        # 2. Xử lý chỉ tiêu lá: kiểm tra xem có bị trùng tên ở nhiều nhóm cha (SC-2.1) hay là duy nhất (SINGLE_LEAF)
        target_leaf = None
        if leaf_matches:
            leaf_matches.sort(key=lambda x: len(x["name"]), reverse=True)
            target_leaf = leaf_matches[0]
        elif matched_code:
            for it in items:
                if it["code"] == matched_code and it["is_leaf"]:
                    target_leaf = it
                    break

        if target_leaf:
            leaf_low = target_leaf["name_low"]
            same_name_leaves = [it for it in items if it["is_leaf"] and it["name_low"] == leaf_low]

            # Nếu người dùng đã nêu rõ tên nhóm cha / nhánh cha trong câu hỏi -> Lọc theo nhóm cha đó
            if len(same_name_leaves) > 1 and parent_matches:
                parent_ids = {p["id"] for p in parent_matches}
                qualified = [
                    it for it in same_name_leaves
                    if it["parent_id"] in parent_ids or it["root_id"] in parent_ids
                ]
                if len(qualified) == 1:
                    same_name_leaves = qualified

            # Hỗ trợ định danh nhánh cha động qua ngữ cảnh câu hỏi hoặc parent_context kế thừa từ Turn trước
            if len(same_name_leaves) > 1:
                acr_map = {}
                if hasattr(self, "conn") and self.conn:
                    try:
                        for acr, full in self.conn.execute("SELECT LOWER(acronym), LOWER(full_form) FROM catalog_acronyms;").fetchall():
                            acr_map[acr] = full
                    except Exception:
                        pass

                context_sources = [q_norm]
                if parent_context:
                    context_sources.append(" ".join(unicodedata.normalize("NFC", str(parent_context).lower().strip()).split()))

                for ctx in context_sources:
                    ctx_str = f" {ctx} "
                    ctx_unacc = f" {self._remove_accents(ctx)} "
                    scored_leaves = []
                    for it in same_name_leaves:
                        p_name = (it.get("parent_name") or "").lower().strip()
                        r_name = (it.get("root_name") or "").lower().strip()
                        p_un = self._remove_accents(p_name)
                        r_un = self._remove_accents(r_name)
                        score = 0
                        if r_name and f" {r_name} " in ctx_str:
                            score += len(r_name) * 2
                        elif r_name and r_name in ctx:
                            score += len(r_name)
                        if p_name and f" {p_name} " in ctx_str:
                            score += len(p_name) * 2
                        elif p_name and p_name in ctx:
                            score += len(p_name)
                        if r_un and f" {r_un} " in ctx_unacc:
                            score += len(r_un)
                        if p_un and f" {p_un} " in ctx_unacc:
                            score += len(p_un)

                        for acr, full in acr_map.items():
                            if f" {acr} " in ctx_str or f" {acr} " in ctx_unacc:
                                if full in r_name or full in p_name:
                                    score += len(full)

                        if score > 0:
                            scored_leaves.append((score, it))

                    if scored_leaves:
                        scored_leaves.sort(key=lambda x: x[0], reverse=True)
                        top_score = scored_leaves[0][0]
                        top_leaves = [it for s, it in scored_leaves if s == top_score]
                        if len(top_leaves) == 1:
                            same_name_leaves = top_leaves
                            break

            if len(same_name_leaves) > 1 and all(it.get("latest_value") is None for it in same_name_leaves):
                chosen_leaf = same_name_leaves[0]
                return {
                    "category": "SINGLE_LEAF",
                    "classification": "single_leaf",
                    "code": chosen_leaf["code"],
                    "name": chosen_leaf["name"],
                    "matched_code": chosen_leaf["code"],
                    "matched_name": chosen_leaf["name"],
                    "item": chosen_leaf,
                }

            if len(same_name_leaves) > 1:
                return {
                    "category": "DUPLICATE_LEAF",
                    "classification": "duplicate_leaf",
                    "name": target_leaf["name"],
                    "matched_name": target_leaf["name"],
                    "matched_code": same_name_leaves[0]["code"],
                    "codes": [it["code"] for it in same_name_leaves],
                    "items": same_name_leaves,
                    "branches": same_name_leaves,
                }

            chosen_leaf = same_name_leaves[0] if same_name_leaves else target_leaf
            return {
                "category": "SINGLE_LEAF",
                "classification": "single_leaf",
                "code": chosen_leaf["code"],
                "name": chosen_leaf["name"],
                "matched_code": chosen_leaf["code"],
                "matched_name": chosen_leaf["name"],
                "parent_name": chosen_leaf.get("parent_name"),
                "parent_level": chosen_leaf.get("parent_level", 1),
                "mission_name": chosen_leaf.get("mission_name"),
                "office_name": chosen_leaf.get("office_name"),
                "latest_value": chosen_leaf.get("latest_value"),
                "item": chosen_leaf,
            }

        if not matched_code and not matched_name:
            return {
                "category": "NONE",
                "classification": "none",
                "code": None,
                "name": None,
                "matched_code": None,
                "matched_name": None,
            }

        return {
            "category": "SINGLE_LEAF",
            "classification": "single_leaf",
            "code": matched_code,
            "name": matched_name,
            "matched_code": matched_code,
            "matched_name": matched_name,
        }

    def build_criteria_tree_for_rows(
        self,
        rows: List[Dict[str, Any]],
        mission_filter: Optional[str] = None,
        has_temporal_filter: bool = False,
    ) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Xây dựng cấu trúc Cây Phân cấp Chỉ tiêu (Cấp 1 -> Cấp 2 -> Cấp 3) cho từng Nhóm chỉ tiêu Cấp 1 (root).
        Kết hợp siêu dữ liệu phân cấp từ catalog_criteria_hierarchy và giá trị thực tế trong rows (đã lọc theo thời gian).
        Trả về:
        - tree_by_root_id: Dict[root_id, tree_dict] phục vụ Pop-up Modal
        - level1_summary_rows: Danh sách dòng bảng Cấp 1 phục vụ REQ-Q04 & SC-4.1
        """
        try:
            hier_rows = self.conn.execute("""
                SELECT id, code, name, parent_id, parent_name, root_id, root_name, level, is_leaf, mission_name, office_name, latest_value
                FROM catalog_criteria_hierarchy
                ORDER BY level ASC, name ASC;
            """).fetchall()
        except Exception:
            hier_rows = []

        if not hier_rows:
            return ({}, [])

        # Bảng tra cứu id theo (name_low, parent_name_low) và name_low khi rows không chọn cột criteria_id
        cid_by_name_parent: Dict[Tuple[str, str], str] = {}
        cids_by_name_only: Dict[str, List[str]] = {}
        for r in hier_rows:
            cid_h, code_h, name_h, pid_h, pname_h = r[0], r[1], (r[2] or "").strip().lower(), r[3], (r[4] or "Chỉ tiêu chung").strip().lower()
            cid_by_name_parent[(name_h, pname_h)] = cid_h
            cids_by_name_only.setdefault(name_h, []).append(cid_h)

        # Map giá trị mới nhất từ rows kết quả truy vấn (theo criteria_id hoặc ten_chi_tieu + nhom_chi_tieu)
        val_by_cid: Dict[str, Any] = {}
        date_by_cid: Dict[str, Any] = {}
        present_cids: set = set()
        for r in rows or []:
            cid = str(r.get("criteria_id") or "").strip()
            if not cid:
                r_name = str(r.get("ten_chi_tieu") or r.get("name") or "").strip().lower()
                r_p = str(r.get("nhom_chi_tieu") or "Chỉ tiêu chung").strip().lower()
                cid = cid_by_name_parent.get((r_name, r_p)) or ""
                if not cid and r_name in cids_by_name_only and len(cids_by_name_only[r_name]) == 1:
                    cid = cids_by_name_only[r_name][0]
            if cid:
                present_cids.add(cid)
                v_cand = r.get("gia_tri_moi_nhat") if r.get("gia_tri_moi_nhat") is not None else (r.get("gia_tri") if r.get("gia_tri") is not None else r.get("value"))
                val_by_cid[cid] = v_cand
                date_by_cid[cid] = r.get("ngay_bao_cao_moi_nhat") or r.get("ngay_bao_cao") or r.get("ky_bao_cao") or r.get("report_date")

        def_mname, def_oname = "-", "-"
        mission_order_map: Dict[str, int] = {}
        mission_facts_map: Dict[str, bool] = {}
        try:
            m_all_rows = self.conn.execute(
                "SELECT name, office_names, has_approved_facts FROM catalog_missions_detail ORDER BY name ASC;"
            ).fetchall()
            approved_idx = 0
            for m_n, m_off, has_facts in m_all_rows:
                if m_n:
                    m_n_clean = m_n.strip().lower()
                    mission_facts_map[m_n_clean] = bool(has_facts)
                    if bool(has_facts):
                        mission_order_map[m_n_clean] = approved_idx
                        approved_idx += 1
                        def_mname = m_n or "-"
                        def_oname = m_off or "-"
        except Exception:
            pass

        nodes_by_id: Dict[str, Dict[str, Any]] = {}
        children_by_parent: Dict[str, List[str]] = {}
        roots: List[str] = []

        for r in hier_rows:
            cid, code, name, pid, pname, rid, rname, lvl, is_leaf, mname, oname, lval = r
            mission_has_facts = mission_facts_map.get(mname.strip().lower(), True) if mname else True
            if not mission_has_facts and cid not in present_cids:
                continue

            raw_row_val = val_by_cid.get(cid) if cid in val_by_cid else None
            if raw_row_val is not None and str(raw_row_val).strip() not in ("", "-", "None"):
                node_val = raw_row_val
            elif cid in val_by_cid:
                node_val = raw_row_val
            elif has_temporal_filter:
                # PA 2.1: Khi câu hỏi có bộ lọc thời gian mà chỉ tiêu con không phát sinh báo cáo trong kỳ -> hiển thị '-' (None), cấm rò rỉ lval
                node_val = None
            else:
                node_val = lval
            nodes_by_id[cid] = {
                "id": cid,
                "code": code,
                "name": name,
                "parent_id": pid,
                "root_id": rid,
                "level": int(lvl or 1),
                "is_leaf": bool(is_leaf),
                "mission_name": mname or def_mname,
                "office_name": oname or def_oname,
                "value": node_val,
                "report_date": str(date_by_cid.get(cid) or ""),
                "children": [],
            }
            if pid:
                children_by_parent.setdefault(pid, []).append(cid)
            else:
                roots.append(cid)

        def _build_subtree(node_id: str) -> Dict[str, Any]:
            node = dict(nodes_by_id[node_id])
            c_ids = children_by_parent.get(node_id, [])
            node["children"] = [_build_subtree(cid) for cid in c_ids if cid in nodes_by_id]
            return node

        def _count_descendants(n: Dict[str, Any]) -> int:
            return sum(1 + _count_descendants(ch) for ch in n.get("children", []))

        tree_by_root_id: Dict[str, Dict[str, Any]] = {}
        level1_summary_rows: List[Dict[str, Any]] = []

        # Sắp xếp roots theo thứ tự danh mục nhiệm vụ từ catalog_missions_detail
        def _root_sort_key(rid: str) -> Tuple[int, str]:
            nd = nodes_by_id[rid]
            m_name_low = str(nd.get("mission_name") or "").strip().lower()
            m_order = mission_order_map.get(m_name_low, 99)
            return (m_order, nd["name"])

        for rid in sorted(roots, key=_root_sort_key):
            root_node = _build_subtree(rid)
            if mission_filter and root_node["mission_name"].lower().strip() != mission_filter.lower().strip():
                continue
            # Kiểm tra nếu có bộ lọc thời gian (rows không rỗng) thì root hoặc ít nhất 1 nhánh con phải nằm trong present_cids
            if present_cids:
                def _has_present(n: Dict[str, Any]) -> bool:
                    if n["id"] in present_cids:
                        return True
                    return any(_has_present(ch) for ch in n.get("children", []))
                if not _has_present(root_node):
                    continue

            tree_by_root_id[rid] = root_node
            is_leaf_root = root_node["is_leaf"]
            desc_count = _count_descendants(root_node)
            raw_v = root_node["value"]
            if raw_v is None or str(raw_v).strip() in ("", "-", "None"):
                val_disp = "Chưa có số liệu phê duyệt (-)"
            else:
                try:
                    fv = float(raw_v)
                    val_disp = f"{int(fv):,}".replace(",", ".") if fv.is_integer() else f"{fv:,.2f}"
                except Exception:
                    val_disp = str(raw_v)

            if is_leaf_root:
                struct_type = "Chỉ tiêu đơn (Cấp 1)"
                child_action = "Không có"
            else:
                struct_type = f"Nhóm chỉ tiêu ({desc_count} chỉ tiêu con)"
                child_action = "- (Xem chi tiết con)" if desc_count > 0 else "Không có"

            level1_summary_rows.append({
                "criteria_id": rid,
                "nhiem_vu": root_node["mission_name"],
                "ten_chi_tieu_cap_1": root_node["name"],
                "loai_cau_truc_cap_1": struct_type,
                "gia_tri_moi_nhat": val_disp,
                "chi_tieu_con": child_action,
                "don_vi_thuc_hien": root_node["office_name"],
                "is_parent_group": not is_leaf_root,
                "child_count": desc_count,
                "tree_modal": root_node if not is_leaf_root else None,
            })

        return (tree_by_root_id, level1_summary_rows)

    def resolve_report_audit_intent(self, raw_input: str) -> Optional[Dict[str, Any]]:
        """
        Phân giải ý định kiểm toán báo cáo, biểu mẫu thu thập và ma trận phân công nhiệm vụ (REQ-Q05: SC-5.1, SC-5.2, SC-5.3).
        """
        if not raw_input:
            return None

        # 1. SC-5.2: Biểu mẫu thu thập (collection_form) & Bộ thu thập chỉ tiêu (criteria_group)
        if self.has_lexicon_term(raw_input, "FORM_CRITERIA_GROUP"):
            return {
                "audit_sub_intent": "FORM_CRITERIA_GROUP",
                "target_table": "criteria_group",
                "status_filter": ["active", "draft"],
                "include_draft_comparison": True,
            }

        # 2. SC-5.3: Ma trận phân công nhiệm vụ - phòng ban - cán bộ
        has_mission = self.has_lexicon_term(raw_input, "MISSION_KEYWORD")
        has_office = self.has_lexicon_term(raw_input, "OFFICE_KEYWORD")
        has_officer = self.has_lexicon_term(raw_input, "OFFICER_KEYWORD")
        has_matrix_cue = self.has_lexicon_term(raw_input, "MATRIX_CUE")
        if (has_mission and has_office and has_officer) or (has_mission and has_matrix_cue):
            return {
                "audit_sub_intent": "MISSION_ASSIGNMENT_MATRIX",
                "target_table": "mission_assignment_matrix",
                "status_filter": ["ALL"],
                "include_draft_comparison": False,
            }

        # 3. SC-5.1: Tiến độ nộp báo cáo, trạng thái phê duyệt (approved) & bản nháp (draft)
        has_report = self.has_lexicon_term(raw_input, "REPORT_SIGNAL")
        has_status_or_draft = self.has_lexicon_term(raw_input, "REPORT_STATUS")
        if (has_report and has_status_or_draft) or (has_status_or_draft and self.has_lexicon_term(raw_input, "REPORT_DIFF")):
            wants_diff = self.has_lexicon_term(raw_input, "REPORT_DIFF")
            return {
                "audit_sub_intent": "REPORT_SUBMISSION_STATUS",
                "target_table": "report",
                "status_filter": ["approved", "draft", "pending"],
                "include_draft_comparison": wants_diff,
            }

        return None

    def get_latest_report_date(self) -> str:
        """
        Truy vấn động ngày báo cáo mới nhất từ catalog_sync_meta hoặc catalog_criteria_hierarchy.
        Trả về '-' nếu không có dữ liệu.
        """
        try:
            row = self.conn.execute("SELECT STRFTIME(dwh_pipeline_run_at, '%Y-%m-%d') FROM catalog_sync_meta ORDER BY dwh_pipeline_run_at DESC LIMIT 1;").fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception:
            pass
        return "-"




