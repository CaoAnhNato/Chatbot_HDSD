"""
Module: IPGov_Chatbot/schemas/canonical_query_frame.py
Chức năng: Khế ước dữ liệu CanonicalQueryFrameDTO (CQF) bằng Pydantic v2.
Căn cứ:
- Blueprint: remediation_and_normalization_plan.md
- Mô hình Khung Ngữ Nghĩa Hai Tầng (Two-Stage Canonical Semantic Normalization)
- Tuân thủ Pydantic v2 strict typing.
"""

from __future__ import annotations

import calendar
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field


class TemporalSlotSpec(BaseModel):
    """
    Khế ước Ngữ nghĩa Thời gian Lai ghép (PA 4.1 - Neuro-Symbolic Calendar Contract).
    LLM CoT trích xuất cấu trúc ngữ nghĩa thời gian tổng quát; Python `calendar` tính toán
    tất định ngày đầu kỳ / cuối kỳ (xử lý chính xác năm nhuận, độ dài từng tháng/quý).
    """
    model_config = ConfigDict(extra="ignore")

    granularity: Literal[
        "NONE",
        "EXACT_DATE",
        "MONTH",
        "MONTH_SPAN",
        "QUARTER",
        "QUARTER_SPAN",
        "HALF_YEAR",
        "YTD",
        "YEAR",
    ] = Field(default="NONE", description="Độ mịn thời gian trích xuất từ câu hỏi")
    year: int = Field(default=2026, description="Năm báo cáo mục tiêu")
    end_year: Optional[int] = Field(default=None, description="Năm kết thúc nếu khoảng thời gian vắt qua 2 năm")
    month: Optional[int] = Field(default=None, description="Tháng cụ thể (1..12)")
    day: Optional[int] = Field(default=None, description="Ngày cụ thể trong tháng (1..31)")
    start_month: Optional[int] = Field(default=None, description="Tháng bắt đầu (1..12)")
    end_month: Optional[int] = Field(default=None, description="Tháng kết thúc (1..12)")
    quarter: Optional[int] = Field(default=None, description="Quý (1..4)")
    end_quarter: Optional[int] = Field(default=None, description="Quý kết thúc (1..4) cho liên quý")
    half: Optional[int] = Field(default=None, description="Nửa năm: 1 (6 tháng đầu năm), 2 (6 tháng cuối năm)")

    def to_calendar_bounds(self) -> Dict[str, Any]:
        """
        Quy đổi tất định cấu trúc ngữ nghĩa thời gian sang (date_from, date_to, month_filter, specific_date, year_code)
        bằng thư viện chuẩn `calendar.monthrange`.
        """
        y1 = self.year if 1900 <= int(self.year or 2026) <= 2100 else 2026
        y2 = self.end_year if (self.end_year and 1900 <= int(self.end_year) <= 2100) else y1
        out: Dict[str, Any] = {
            "year_code": str(y2),
            "date_from": None,
            "date_to": None,
            "month_filter": None,
            "specific_date": None,
        }

        def _last_day(yr: int, mo: int) -> int:
            mo_clamped = max(1, min(12, int(mo)))
            return calendar.monthrange(yr, mo_clamped)[1]

        gran = (self.granularity or "NONE").upper()
        if gran == "EXACT_DATE" and self.month and self.day:
            m_c = max(1, min(12, int(self.month)))
            d_c = max(1, min(_last_day(y1, m_c), int(self.day)))
            out["specific_date"] = f"{y1:04d}-{m_c:02d}-{d_c:02d}"
        elif gran == "MONTH" and self.month:
            m_c = max(1, min(12, int(self.month)))
            out["month_filter"] = m_c
        elif gran == "MONTH_SPAN" and self.start_month and self.end_month:
            m1 = max(1, min(12, int(self.start_month)))
            m2 = max(1, min(12, int(self.end_month)))
            if y2 == y1 and m2 < m1:
                m1, m2 = m2, m1
            out["date_from"] = f"{y1:04d}-{m1:02d}-01"
            out["date_to"] = f"{y2:04d}-{m2:02d}-{_last_day(y2, m2):02d}"
        elif gran in ("QUARTER", "QUARTER_SPAN") and self.quarter:
            q1 = max(1, min(4, int(self.quarter)))
            q2 = max(q1, min(4, int(self.end_quarter))) if self.end_quarter else q1
            m1 = (q1 - 1) * 3 + 1
            m2 = q2 * 3
            out["date_from"] = f"{y1:04d}-{m1:02d}-01"
            out["date_to"] = f"{y2:04d}-{m2:02d}-{_last_day(y2, m2):02d}"
        elif gran == "HALF_YEAR" and self.half in (1, 2):
            if self.half == 1:
                out["date_from"] = f"{y1:04d}-01-01"
                out["date_to"] = f"{y1:04d}-06-{_last_day(y1, 6):02d}"
            else:
                out["date_from"] = f"{y1:04d}-07-01"
                out["date_to"] = f"{y1:04d}-12-{_last_day(y1, 12):02d}"
        elif gran == "YTD":
            out["date_from"] = f"{y1:04d}-01-01"
            out["date_to"] = f"{y1:04d}-12-{_last_day(y1, 12):02d}"
        return out


class CanonicalIntentEnum(str, Enum):
    """Các bài toán nghiệp vụ DWH chuẩn tắc."""
    METRIC_POINT_INQUIRY = "METRIC_POINT_INQUIRY"     # Tra cứu giá trị 1 hoặc nhiều chỉ tiêu tại điểm thời gian
    PARENT_CHILDREN_BREAKDOWN = "PARENT_CHILDREN_BREAKDOWN" # Liệt kê/phân rã danh mục chỉ tiêu con trực thuộc chỉ tiêu cha
    CROSS_BRANCH_COMPARISON = "CROSS_BRANCH_COMPARISON"     # So sánh/liệt kê chỉ tiêu con trên nhiều nhánh cha khác nhau
    METRIC_NUMERIC_CALCULATION = "METRIC_NUMERIC_CALCULATION" # Tính toán / tổng hợp số liệu chỉ tiêu KTXH
    METRIC_TOP_K = "METRIC_TOP_K"                     # Xếp hạng Top-K, DENSE_RANK chỉ tiêu cao nhất/thấp nhất
    METRIC_GROWTH_YOY = "METRIC_GROWTH_YOY"           # So sánh tăng trưởng giữa 2 đợt hoặc 2 năm (YoY, QoQ)
    DIMENSION_LISTING = "DIMENSION_LISTING"           # Liệt kê danh mục biểu mẫu, nhiệm vụ, đề án
    METADATA_EXPLORATION = "METADATA_EXPLORATION"     # Khám phá danh mục metadata (tỉnh thành province, danh sách chỉ tiêu criteria...)
    ENTITY_ATTRIBUTE_LOOKUP = "ENTITY_ATTRIBUTE_LOOKUP" # Tra cứu thuộc tính thực thể (đơn vị thực hiện, tỉnh thực hiện...)
    RELATIONAL_EXPLORATION = "RELATIONAL_EXPLORATION"   # Khám phá quan hệ liên bảng (xã phường theo tỉnh, nhiệm vụ theo phòng...)
    OFFICER_ASSIGNMENT = "OFFICER_ASSIGNMENT"         # Tra cứu cán bộ phụ trách nhiệm vụ
    REPORT_STATUS_AUDIT = "REPORT_STATUS_AUDIT"       # Tra cứu tiến độ nộp báo cáo, đợt nộp
    REPORT_FORM_MISSION_AUDIT = "REPORT_FORM_MISSION_AUDIT" # Tra cứu tiến độ báo cáo, biểu mẫu thu thập & ma trận phân công nhiệm vụ (REQ-Q05)
    CAPABILITY_INTRO = "CAPABILITY_INTRO"             # Chào hỏi, giới thiệu tính năng hệ thống
    GREETING_FAREWELL = "GREETING_FAREWELL"           # Chào hỏi & Tạm biệt / cảm ơn lịch sự
    OUT_OF_SCOPE = "OUT_OF_SCOPE"                     # Ngoài phạm vi kho DWH


class SemanticQueryIntentDTO(BaseModel):
    """DTO định tuyến ngữ nghĩa bằng Model-Driven LLM Parser."""
    model_config = ConfigDict(extra="ignore")

    is_out_of_scope: bool = Field(
        default=False,
        description="True nếu câu hỏi là toán học, chitchat, hoặc không liên quan đến kho dữ liệu DWH"
    )
    direct_answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời trực tiếp nếu là câu hỏi toán học hoặc chào hỏi"
    )
    intent: Literal[
        "METRIC_NUMERIC_CALCULATION",
        "METRIC_POINT_INQUIRY",
        "PARENT_CHILDREN_BREAKDOWN",
        "CROSS_BRANCH_COMPARISON",
        "ENTITY_ATTRIBUTE_LOOKUP",
        "RELATIONAL_EXPLORATION",
        "METADATA_EXPLORATION",
        "DIMENSION_LISTING",
        "REPORT_FORM_MISSION_AUDIT",
        "CAPABILITY_INTRO",
        "GREETING_FAREWELL",
        "OUT_OF_SCOPE",
    ] = Field(
        default="METRIC_NUMERIC_CALCULATION",
        description="Ý định phân loại chính của mô hình"
    )
    subject_entity: Optional[str] = Field(
        default=None,
        description="Thực thể chính (tên chỉ tiêu, tên tỉnh, tên phòng ban, tên nhiệm vụ)"
    )
    target_attribute: Optional[str] = Field(
        default=None,
        description="Thuộc tính cần tra cứu (đơn vị thực hiện, tỉnh thực hiện, danh sách xã/phường, số liệu)"
    )
    time_filter: Optional[str] = Field(
        default="2026",
        description="Mốc thời gian lọc nếu có"
    )
    spatial_filter: Optional[str] = Field(
        default="68",
        description="Mã địa phương nếu có"
    )
    target_table: Optional[str] = Field(
        default=None,
        description="Bảng đích truy vấn nếu có (province, criteria, deparment, office, mission, collection_form, user, ward, fact_report_criteria)"
    )
    exclude_entities: List[str] = Field(
        default_factory=list,
        description="Danh sách thực thể loại trừ nếu có"
    )
    is_inventory_query: bool = Field(
        default=False,
        description="True nếu là câu hỏi kiểm kê danh mục"
    )
    is_conversational_only: bool = Field(
        default=False,
        description="True nếu câu hỏi là thuần chào hỏi/tạm biệt/giao tiếp"
    )
    temporal_slot: Optional[dict] = Field(
        default=None,
        description="Dải thời gian chuẩn hóa: date_from, date_to, year_code, time_grain, start_month, end_month, day"
    )
    target_scope: Optional[str] = Field(
        default=None,
        description="Tên lĩnh vực quản lý (scope_name) trích xuất từ câu hỏi (REQ-Q03)"
    )
    specific_date: Optional[str] = Field(
        default=None,
        description="Ngày báo cáo cụ thể định dạng YYYY-MM-DD nếu người dùng hỏi ngày/tháng cụ thể (SC-2.2)"
    )
    is_level1_hierarchy_view: bool = Field(
        default=False,
        description="True khi liệt kê chỉ tiêu theo khoảng thời gian (REQ-Q01) hoặc chỉ tiêu Cấp 1 của nhiệm vụ (REQ-Q04)"
    )
    is_mixed_multi_metric: bool = Field(
        default=False,
        description="True nếu câu hỏi kết hợp nhiều chỉ tiêu khác bản chất (cần Scatter-Gather)"
    )
    sub_queries: List[str] = Field(
        default_factory=list,
        description="Danh sách truy vấn con cho Scatter-Gather"
    )
    status_filter: Optional[List[str]] = Field(
        default=None,
        description="Danh sách trạng thái báo cáo cần lọc: 'approved', 'draft', 'pending', 'rejected', hoặc 'ALL'"
    )
    audit_sub_intent: Optional[str] = Field(
        default=None,
        description="Phân nhánh con của REQ-Q05: 'REPORT_SUBMISSION_STATUS' (SC-5.1), 'FORM_CRITERIA_GROUP' (SC-5.2), 'MISSION_ASSIGNMENT_MATRIX' (SC-5.3)"
    )
    include_draft_comparison: bool = Field(
        default=False,
        description="True nếu người dùng yêu cầu đối chiếu số liệu giữa bản nháp (draft) và bản đã duyệt (approved)"
    )


class CanonicalQueryFrameDTO(BaseModel):
    """
    Khung Truy Vấn Chuẩn Tắc (Canonical Query Frame - CQF).
    Cấu trúc dữ liệu trung gian chuẩn hóa mọi biến thể câu hỏi tự nhiên về một dạng duy nhất,
    triệt tiêu 100% tính giòn ngôn ngữ trước khi biên dịch SQL tất định.
    """
    model_config = ConfigDict(extra="ignore")

    user_query: str = Field(
        default="",
        description="Nội dung câu hỏi gốc của người dùng sau khi làm sạch"
    )
    intent: CanonicalIntentEnum = Field(
        default=CanonicalIntentEnum.METRIC_POINT_INQUIRY,
        description="Ý định nghiệp vụ DWH được phân loại"
    )
    target_table: str = Field(
        default="fact_report_criteria",
        description="Bảng chính đích phục vụ truy vấn (province, criteria, deparment, office, mission, collection_form, user, ward, fact_report_criteria)"
    )
    is_out_of_scope: bool = Field(
        default=False,
        description="True nếu câu hỏi ngoài phạm vi DWH hoặc câu hỏi toán học/chitchat"
    )
    direct_answer: Optional[str] = Field(
        default=None,
        description="Câu trả lời trực tiếp từ NLU nếu là toán học hoặc ngoài phạm vi"
    )
    subject_entity: Optional[str] = Field(
        default=None,
        description="Thực thể chính trích xuất từ câu hỏi"
    )
    target_attribute: Optional[str] = Field(
        default=None,
        description="Thuộc tính cần tra cứu (đơn vị thực hiện, tỉnh thực hiện, xã phường, số liệu)"
    )
    exclude_entities: List[str] = Field(
        default_factory=list,
        description="Danh sách các thực thể cần loại trừ khỏi truy vấn danh mục (vd: ngoài Lâm Đồng -> ['Lâm Đồng'])"
    )
    search_keyword: Optional[str] = Field(
        default=None,
        description="Từ khóa tìm kiếm theo danh mục nếu có"
    )
    canonical_metric_names: List[str] = Field(
        default_factory=list,
        description="Danh sách tên chỉ tiêu chuẩn tắc sau khi đối chiếu Catalog"
    )
    canonical_metric_ids: List[str] = Field(
        default_factory=list,
        description="Danh sách UUID của chỉ tiêu chuẩn tắc tương ứng"
    )
    raw_metric_mentions: List[str] = Field(
        default_factory=list,
        description="Chuỗi thực thể chỉ tiêu thô trích xuất từ câu hỏi"
    )
    spatial_mention: Optional[str] = Field(
        default=None,
        description="Tên địa danh thô trích xuất từ câu hỏi (phân biệt với từ viết tắt chuyên môn)"
    )
    tenant_code: str = Field(
        default="68",
        description="Mã địa bàn chuẩn hóa (mặc định '68' Lâm Đồng, '79' TP.HCM...)"
    )
    year_code: str = Field(
        default="2026",
        description="Năm báo cáo số liệu ('2026', '2025', '2024')"
    )
    department_code: Optional[str] = Field(
        default=None,
        description="Mã phòng ban / sở ngành cụ thể nếu câu hỏi yêu cầu"
    )
    aggregation_function: Literal["SUM", "AVG", "DENSE_RANK", "COUNT", "NONE"] = Field(
        default="NONE",
        description="Hàm tổng hợp toán học cần áp dụng"
    )
    ambiguity_status: Literal["RESOLVED", "AMBIGUOUS", "NONE"] = Field(
        default="RESOLVED",
        description="Trạng thái phân giải chỉ tiêu: RESOLVED (xác định duy nhất) hoặc AMBIGUOUS (cần Clarification Chips)"
    )
    clarification_candidates: List[str] = Field(
        default_factory=list,
        description="Danh sách các tên chỉ tiêu ứng viên khi ambiguity_status == AMBIGUOUS"
    )
    is_snapshot_dedup_needed: bool = Field(
        default=False,
        description="Cờ yêu cầu áp dụng CTE Window Function rn = 1 để lấy đợt nộp mới nhất"
    )
    sort_direction: Literal["DESC_NULLS_LAST", "ASC", "NONE"] = Field(
        default="NONE",
        description="Chiều sắp xếp kết quả"
    )
    limit: Optional[int] = Field(
        default=None,
        description="Số lượng dòng tối đa cần lấy (chỉ áp dụng khi câu hỏi yêu cầu Top-K tường minh; mặc định None để lấy đầy đủ dữ liệu từ Warehouse)"
    )
    is_empty_year: bool = Field(
        default=False,
        description="Đánh dấu năm trắng dữ liệu (2024, 2025) để trả lời dứt khoát không hallucinate"
    )
    time_series_periods: List[str] = Field(
        default_factory=list,
        description="Các mốc kỳ báo cáo phục vụ so sánh tăng trưởng (vd: 30/06/2026, 30/09/2026)"
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Mốc thời gian bắt đầu lọc cho truy vấn dải thời gian (vd: '2026-03-01')"
    )
    date_to: Optional[str] = Field(
        default=None,
        description="Mốc thời gian kết thúc lọc cho truy vấn dải thời gian"
    )
    month_filter: Optional[int] = Field(
        default=None,
        description="Tháng cần lọc số liệu trong năm (vd: 9 cho tháng 9)"
    )
    specific_date: Optional[str] = Field(
        default=None,
        description="Ngày báo cáo cụ thể định dạng YYYY-MM-DD nếu người dùng hỏi ngày/tháng cụ thể (SC-2.2)"
    )
    target_scope: Optional[str] = Field(
        default=None,
        description="Tên lĩnh vực quản lý (scope_name) trích xuất từ câu hỏi (REQ-Q03)"
    )
    is_level1_hierarchy_view: bool = Field(
        default=False,
        description="True khi liệt kê chỉ tiêu theo khoảng thời gian (REQ-Q01) hoặc chỉ tiêu Cấp 1 của nhiệm vụ (REQ-Q04)"
    )
    clarification_message: Optional[str] = Field(
        default=None,
        description="Thông điệp làm rõ hoặc thông báo chỉ tiêu cha (SC-2.4) / lĩnh vực không tồn tại (SC-3.2)"
    )
    target_office: Optional[str] = Field(
        default=None,
        description="Tên phòng ban / văn phòng cụ thể nếu người dùng chỉ định"
    )
    target_mission: Optional[str] = Field(
        default=None,
        description="Tên nhiệm vụ cụ thể nếu người dùng chỉ định"
    )
    target_position: Optional[str] = Field(
        default=None,
        description="Chức vụ cán bộ nếu có"
    )
    target_user_name: Optional[str] = Field(
        default=None,
        description="Tên cán bộ nếu có"
    )
    target_ward: Optional[str] = Field(
        default=None,
        description="Tên xã phường nếu có"
    )
    is_inventory_query: bool = Field(
        default=False,
        description="True nếu câu hỏi là kiểm kê/khám phá toàn bộ danh mục chỉ tiêu hiện có trong hệ thống (P-03)"
    )
    sub_queries: List[str] = Field(
        default_factory=list,
        description="Danh sách các câu truy vấn con phục vụ Scatter-Gather cho câu hỏi đa chỉ tiêu lai"
    )
    parent_criterion_context: Optional[str] = Field(
        default=None,
        description="Tên chỉ tiêu cha kế thừa từ lượt hỏi trước (SC-2.4 -> SC-2.1 disambiguation)"
    )
    status_filter: Optional[List[str]] = Field(
        default=None,
        description="Danh sách trạng thái báo cáo cần lọc ('approved', 'draft', 'pending', 'rejected', 'ALL')"
    )
    audit_sub_intent: Optional[str] = Field(
        default=None,
        description="Phân nhánh con của REQ-Q05: 'REPORT_SUBMISSION_STATUS' (SC-5.1), 'FORM_CRITERIA_GROUP' (SC-5.2), 'MISSION_ASSIGNMENT_MATRIX' (SC-5.3)"
    )
    include_draft_comparison: bool = Field(
        default=False,
        description="True nếu yêu cầu đối chiếu giữa bản nháp (draft) và bản đã duyệt (approved)"
    )
    blocked_draft_access: bool = Field(
        default=False,
        description="True nếu người dùng cấp thấp bị HBAC chặn quyền xem dữ liệu draft/pending vượt cấp"
    )

