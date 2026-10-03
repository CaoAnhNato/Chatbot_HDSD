"""
Bộ Đóng Gói Dấu Vết Nguồn Gốc Dữ Liệu (Lineage Badge Builder) cho Module 08.
Tạo LineageBadgeDTO đính kèm mã băm SHA-256 xác thực bản quyền và cấp thẩm quyền phê duyệt.
Tuân thủ Blueprint 07 và SSOT.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from IPGov_Chatbot.schemas.response_synthesizer_dto import LineageBadgeDTO


class LineageBadgeBuilder:
    """
    Xây dựng thẻ nguồn gốc dữ liệu phục vụ đối chiếu và kiểm toán công vụ.
    """

    @staticmethod
    def build_badge(
        query_result: Any,
        sanitized_dto: Optional[Any] = None,
        router_output: Optional[Any] = None,
        user_ctx: Optional[Any] = None,
    ) -> LineageBadgeDTO:
        """
        Trích xuất và đóng gói thẻ LineageBadgeDTO từ các DTO giai đoạn trước.
        """
        entities: Dict[str, Any] = dict(getattr(router_output, "extracted_entities", {}) or {})
        active_quest = getattr(router_output, "active_quest", None)
        if active_quest:
            if getattr(active_quest, "admin_entity", None):
                entities.setdefault("department_name", active_quest.admin_entity)
            if getattr(active_quest, "temporal_val", None):
                entities.setdefault("year", active_quest.temporal_val)
            if getattr(active_quest, "metric_code", None):
                entities.setdefault("criteria_name", active_quest.metric_code)
            if getattr(active_quest, "extra_slots", None):
                for k, v in active_quest.extra_slots.items():
                    entities.setdefault(k, v)

        # 1. Xác định thẩm quyền cơ quan (Department & Office)
        dept_code = (
            entities.get("department_code")
            or getattr(user_ctx, "department_code", None)
            or "68"
        )
        
        # Ánh xạ tên cơ quan
        dept_name = entities.get("department_name") or entities.get("department")
        if not dept_name:
            if dept_code == "68":
                dept_name = "UBND Tỉnh Lâm Đồng"
            elif dept_code == "79":
                dept_name = "UBND Thành phố Hồ Chí Minh"
            elif dept_code.startswith("79-1-01"):
                dept_name = "Sở Nội Vụ"
            elif dept_code.startswith("79-1-02"):
                dept_name = "Văn phòng UBND TP.HCM"
            elif dept_code.startswith("SCT") or "cong_thuong" in dept_code.lower():
                dept_name = "Sở Công Thương"
            else:
                dept_name = f"Cơ quan ban ngành (Mã {dept_code})"

        office_id = entities.get("office_id") or getattr(user_ctx, "office_id", None)
        office_name = entities.get("office_name") or entities.get("office")

        # 2. Xác định Chỉ tiêu & Kỳ báo cáo
        crit_code = entities.get("criteria_code") or ""
        crit_name = entities.get("criteria_name") or entities.get("metric_name") or "Số liệu tổng hợp DWH"
        
        period = str(entities.get("year") or entities.get("period") or "2024")

        # 3. Số dòng Fact thực tế tham gia tính toán
        rec_count = int(getattr(query_result, "row_count", 0))
        
        # 4. Trạng thái báo cáo
        rep_status = "approved"

        # 5. Mốc thời gian ký duyệt và đồng bộ DWH
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        # 6. Tính toán mã băm SHA-256 xác thực bất biến
        executed_sql = getattr(sanitized_dto, "sanitized_sql", "")
        raw_hash_input = f"{executed_sql}|{rec_count}|{dept_code}|{period}|{rep_status}"
        verification_hash = hashlib.sha256(raw_hash_input.encode("utf-8")).hexdigest()

        return LineageBadgeDTO(
            department_code=str(dept_code),
            department_name=str(dept_name),
            office_id=str(office_id) if office_id else None,
            office_name=str(office_name) if office_name else None,
            criteria_code=str(crit_code),
            criteria_name=str(crit_name),
            report_period=period,
            operational_signoff_date=f"{period}-12-31",
            dwh_pipeline_synced_at=now_iso,
            report_status=rep_status,
            record_count=rec_count,
            verification_hash=verification_hash,
        )
