"""
Động cơ Template Jinja2 Siêu Tốc (Deterministic Template Engine)
Phục vụ tổng hợp câu trả lời chuẩn BLUF (Bottom Line Up Front) cho Module 08.
Đạt tốc độ < 0.05ms trong bộ nhớ RAM, tiêu thụ 0 token LLM cho 85% câu hỏi chuẩn tắc.
"""

from typing import Any, Dict, List, Optional, Tuple
import jinja2

# Các mẫu Jinja2 tiền biên dịch chuẩn BLUF
TEMPLATE_DEFINITIONS = {
    # 1. Chỉ tiêu đơn lẻ trực tiếp (Direct Metric Single Fact)
    "DIRECT_METRIC": (
        "Theo số liệu báo cáo đã phê duyệt năm {{ period }} của {{ entity_name }}, "
        "{{ metric_name }} là: **{{ value_formatted }}{% if unit %} {{ unit }}{% endif %}**."
    ),

    # 2. Xếp hạng Top-K (Top-K Ranking)
    "RANKING_TOP_K": (
        "Top {{ items|length }} đơn vị có {{ metric_name }} cao nhất năm {{ period }}, "
        "dẫn đầu là **{{ items[0].name }}** ({{ items[0].value_formatted }}{% if unit %} {{ unit }}{% endif %}):\n\n"
        "| Hạng | Đơn vị | Giá trị{% if unit %} ({{ unit }}){% endif %} | Ghi chú |\n"
        "| :---: | :--- | :---: | :--- |\n"
        "{% for item in items -%}"
        "| {{ loop.index }} | {{ item.name }} | {{ item.value_formatted }} | {{ item.note|default('-') }} |\n"
        "{% endfor %}\n"
        "{% if spread_formatted -%}"
        "*Chênh lệch giữa đơn vị dẫn đầu và cuối nhóm là {{ spread_formatted }}{% if unit %} {{ unit }}{% endif %}.*"
        "{% endif %}"
    ),

    # 2b. Danh sách phân rã danh mục chỉ tiêu (Breakdown List)
    "BREAKDOWN_LIST": (
        "Danh sách {{ items|length }} chỉ tiêu theo số liệu báo cáo năm {{ period }}{% if entity_name %} của {{ entity_name }}{% endif %}:\n\n"
        "| STT | Tên chỉ tiêu | Giá trị{% if unit %} ({{ unit }}){% endif %} |\n"
        "| :---: | :--- | :---: |\n"
        "{% for item in items -%}"
        "| {{ loop.index }} | {{ item.name }} | **{{ item.value_formatted }}** |\n"
        "{% endfor %}"
    ),


    # 3. So sánh chuỗi thời gian (Temporal YoY/MoM Comparison)
    "TEMPORAL_COMPARISON": (
        "{{ metric_name }} năm {{ period_2 }} đạt **{{ val_2_formatted }}{% if unit %} {{ unit }}{% endif %}**, "
        "so với năm {{ period_1 }} ({{ val_1_formatted }}{% if unit %} {{ unit }}{% endif %}) "
        "{{ delta_direction }} {{ delta_abs_formatted }}{% if unit %} {{ unit }}{% endif %}"
        "{% if growth_pct_text %} ({{ growth_pct_text }}){% endif %}.\n\n"
        "| Kỳ báo cáo | Giá trị{% if unit %} ({{ unit }}){% endif %} | Biến động tuyệt đối | Tốc độ tăng trưởng |\n"
        "| :--- | :---: | :---: | :---: |\n"
        "| Năm {{ period_1 }} | {{ val_1_formatted }} | - | Kỳ gốc |\n"
        "| Năm {{ period_2 }} | {{ val_2_formatted }} | {{ delta_sign }}{{ delta_abs_formatted }} | {{ growth_pct_text|default('N/A') }} |\n\n"
        "{% if small_base_note -%}"
        "*Lưu ý: {{ small_base_note }}*"
        "{% endif %}"
    ),

    # 4. Tỷ trọng bộ phận so với toàn thể (Part-to-Whole Ratio)
    "PART_TO_WHOLE": (
        "Trong tổng số {{ total_val_formatted }}{% if unit %} {{ unit }}{% endif %} toàn tỉnh năm {{ period }}, "
        "{{ entity_name }} chiếm tỷ trọng **{{ share_pct }}%** ({{ entity_val_formatted }}{% if unit %} {{ unit }}{% endif %})."
    ),

    # 5. Trạng thái phê duyệt báo cáo (Report Approval Status)
    "REPORT_STATUS": (
        "Báo cáo {{ form_name|default('thống kê') }} của {{ entity_name }} kỳ {{ period }} "
        "hiện ở trạng thái: **{{ status_vietnamese }}**{% if form_code %} (Mã biểu: {{ form_code }}){% endif %}.\n"
        "{% if signoff_date %}*Thời điểm ký số phê duyệt: {{ signoff_date }}*{% endif %}"
    ),

    # 5b. Danh sách trạng thái báo cáo (Report Status List)
    "REPORT_STATUS_LIST": (
        "Danh sách {{ reports|length }} báo cáo của các đơn vị kỳ {{ period }}:\n\n"
        "| STT | Mã báo cáo | Đơn vị | Trạng thái | Ngày nộp |\n"
        "| :---: | :--- | :--- | :---: | :---: |\n"
        "{% for r in reports -%}"
        "| {{ loop.index }} | `{{ r.code }}` | {{ r.department }} | **{{ r.status }}** | {{ r.date }} |\n"
        "{% endfor %}"
    ),

    # 6. Danh mục biểu mẫu thu thập dữ liệu (Collection Form Discovery)
    "COLLECTION_FORM": (
        "Danh mục {{ forms|length }} biểu mẫu thu thập đang kích hoạt trong năm {{ period }}:\n\n"
        "| STT | Mã biểu | Tên biểu mẫu | Kỳ báo cáo | Cơ quan phụ trách |\n"
        "| :---: | :---: | :--- | :---: | :--- |\n"
        "{% for f in forms -%}"
        "| {{ loop.index }} | `{{ f.code }}` | {{ f.name }} | {{ f.period|default(period) }} | {{ f.agency|default('Sở ngành liên quan') }} |\n"
        "{% endfor %}"
    ),

    # 7. Kiểm toán bất thường dữ liệu (Data Quality / Anomaly Audit)
    "DATA_ANOMALY": (
        "Kết quả rà soát dữ liệu năm {{ period }} ghi nhận **{{ anomalies|length }}** trường hợp "
        "có dấu hiệu bất thường (để trống hoặc bằng 0):\n\n"
        "| STT | Đơn vị | Chỉ tiêu | Giá trị ghi nhận | Trạng thái rà soát |\n"
        "| :---: | :--- | :--- | :---: | :--- |\n"
        "{% for a in anomalies -%}"
        "| {{ loop.index }} | {{ a.entity }} | {{ a.metric }} | `{{ a.value }}` | {{ a.status|default('Cần kiểm tra') }} |\n"
        "{% endfor %}"
    ),

    # 8. Phân công cán bộ phụ trách nhiệm vụ (User Mission)
    "USER_MISSION": (
        "Danh sách {{ missions|length }} nhiệm vụ và cán bộ phụ trách trong kỳ:\n\n"
        "| STT | Cán bộ phụ trách | Nhiệm vụ / Chỉ tiêu | Phòng ban | Trạng thái |\n"
        "| :---: | :--- | :--- | :--- | :---: |\n"
        "{% for m in missions -%}"
        "| {{ loop.index }} | **{{ m.assignee }}** | {{ m.task }} | {{ m.office|default('-') }} | {{ m.status|default('Đang thực hiện') }} |\n"
        "{% endfor %}"
    ),

    # 9. Mốc đồng bộ kho dữ liệu (ETL Pipeline Freshness)
    "ETL_FRESHNESS": (
        "Dữ liệu kho DWH được đồng bộ gần nhất lúc: **{{ last_synced_at }}** "
        "(Mô hình: `{{ model_name|default('dwh_internal') }}`, Trạng thái: **{{ status_vietnamese }}**)."
    ),

    # 10. Thông báo tập kết quả rỗng phòng vệ (Empty Result Safe Guard)
    "EMPTY_RESULT": (
        "Không tìm thấy bản ghi số liệu đã được phê duyệt cho yêu cầu tra cứu trong kho DWH{% if query_year %} trong năm **{{ query_year }}**{% endif %}. "
        "Vui lòng kiểm tra lại mốc thời gian hoặc trạng thái duyệt báo cáo của đơn vị.{% if suggested_year %}\n\n"
        "💡 **Gợi ý tra cứu:** Hiện tại kho DWH đang có dữ liệu số liệu đầy đủ đã phê duyệt của **năm {{ suggested_year }}**. Đồng chí có thể tra cứu theo mốc thời gian này.{% endif %}"
    ),
}


def vn_format_num(val: Any, decimals: int = 2) -> str:
    """
    Định dạng số theo quy chuẩn thống nhất:
    - Phân cách hàng nghìn: dấu phẩy ',' (ví dụ: 1,320)
    - Phân cách thập phân: dấu chấm '.' (ví dụ: 12.5)
    - Năm lịch 4 chữ số (1900 - 2099): TUYỆT ĐỐI không phân cách (giữ nguyên '2026')
    """
    if val is None or val == "":
        return "0"

    str_val = str(val).strip()

    # 1. Bảo vệ năm lịch 4 chữ số
    if str_val.isdigit() and len(str_val) == 4 and 1900 <= int(str_val) <= 2099:
        return str_val

    try:
        f_val = float(val)
        # Nếu là số nguyên và nằm trong khoảng năm lịch 1900-2099 (và chuỗi ban đầu có 4 ký tự)
        if f_val.is_integer() and 1900 <= int(f_val) <= 2099 and len(str_val.split(".")[0]) == 4:
            return str(int(f_val))

        if f_val.is_integer():
            # Số nguyên: 1234567 -> 1,234,567
            return f"{int(f_val):,}"
        else:
            # Số thực: 1234.56 -> 1,234.56
            formatted = f"{f_val:,.{decimals}f}"
            if "." in formatted:
                int_part, dec_part = formatted.split(".")
                dec_clean = dec_part.rstrip("0")
                return f"{int_part}.{dec_clean}" if dec_clean else int_part
            return formatted
    except (ValueError, TypeError):
        return str(val)


def vn_status_translate(status_code: str) -> str:
    """Chuyển đổi trạng thái hệ thống sang tiếng Việt chuẩn công vụ."""
    st = str(status_code).lower().strip()
    mapping = {
        "approved": "Đã phê duyệt",
        "pending": "Chờ phê duyệt",
        "draft": "Dự thảo",
        "rejected": "Bị từ chối",
        "success": "Thành công",
        "failed": "Thất bại",
        "active": "Đang kích hoạt",
        "inactive": "Tạm dừng",
    }
    return mapping.get(st, status_code)


def safe_percentage(val_2: float, val_1: float) -> Tuple[Optional[float], str, Optional[str]]:
    """
    Tính toán tỷ lệ tăng trưởng an toàn, phòng vệ Small Base Effect và ZeroDivisionError.
    Trả về: (growth_pct, growth_text, small_base_note)
    """
    delta = val_2 - val_1
    if val_1 == 0:
        return None, "Không tính toán % tăng trưởng", "Kỳ gốc ghi nhận 0, không xác định được tỷ lệ % tăng trưởng (chỉ đối chiếu chênh lệch tuyệt đối)."
    
    growth_pct = (delta / val_1) * 100.0
    sign = "+" if growth_pct > 0 else ""
    growth_text = f"tăng {sign}{growth_pct:.1f}%" if growth_pct >= 0 else f"giảm {growth_pct:.1f}%"

    small_base_note = None
    if 0 < val_1 < 5:
        small_base_note = f"Số liệu kỳ gốc nhỏ ({val_1}), tỷ lệ biến động {growth_text} có thể mang tính đột biến toán học."

    return round(growth_pct, 2), growth_text, small_base_note


class JinjaSlotEngine:
    """
    Động cơ render mẫu Jinja2 tiền biên dịch trong bộ nhớ RAM.
    """

    def __init__(self):
        # Khởi tạo môi trường Jinja2 độc lập, an toàn
        self.env = jinja2.Environment(
            loader=jinja2.DictLoader(TEMPLATE_DEFINITIONS),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Đăng ký các filters tùy chỉnh
        self.env.filters["vn_format"] = vn_format_num
        self.env.filters["vn_status"] = vn_status_translate

    def render(self, template_key: str, context: Dict[str, Any]) -> str:
        """Render nội dung từ template_key với context cụ thể."""
        if template_key not in TEMPLATE_DEFINITIONS:
            raise KeyError(f"Template '{template_key}' không tồn tại trong JinjaSlotEngine.")
        template = self.env.get_template(template_key)
        return template.render(**context).strip()

    def try_render_dwh_result(
        self,
        query_result: Any,
        router_output: Any,
        sanitized_dto: Optional[Any] = None,
    ) -> Optional[Tuple[str, bool, str]]:
        """
        Thử nghiệm đối chiếu kết quả DWH với các mẫu câu hỏi thường gặp.
        Nếu khớp: Trả về (content_markdown, table_rendered, template_name)
        Nếu không khớp: Trả về None để chuyển tiếp sang LLM Synthesizer.
        """
        # 1. Phòng vệ tập kết quả rỗng
        if getattr(query_result, "is_empty", False) or getattr(query_result, "row_count", 0) == 0:
            return self.render("EMPTY_RESULT", {}), False, "EMPTY_RESULT"

        rows = getattr(query_result, "rows", [])
        if not rows:
            return self.render("EMPTY_RESULT", {}), False, "EMPTY_RESULT"

        route_val = str(getattr(router_output, "route", ""))
        intent_val = str(getattr(router_output, "intent", ""))
        entities = dict(getattr(router_output, "extracted_entities", {}) or {})
        active_quest = getattr(router_output, "active_quest", None)
        if active_quest:
            if getattr(active_quest, "admin_entity", None):
                entities.setdefault("department_name", active_quest.admin_entity)
                entities.setdefault("department", active_quest.admin_entity)
            if getattr(active_quest, "temporal_val", None):
                entities.setdefault("year", active_quest.temporal_val)
                entities.setdefault("period", active_quest.temporal_val)
            if getattr(active_quest, "metric_code", None):
                entities.setdefault("metric_name", active_quest.metric_code)
                entities.setdefault("criteria_name", active_quest.metric_code)
            if getattr(active_quest, "extra_slots", None):
                for k, v in active_quest.extra_slots.items():
                    entities.setdefault(k, v)

        # Trích xuất metadata bổ trợ
        period = entities.get("year") or entities.get("period") or "2024"
        metric_name = entities.get("metric_name") or entities.get("criteria_name") or "Chỉ tiêu"
        entity_name = entities.get("department_name") or entities.get("department") or "UBND Tỉnh"
        unit = entities.get("unit") or ""

        # 2. Xử lý mẫu Mốc ETL Freshness
        if "freshness" in intent_val.lower() or "pipeline" in intent_val.lower() or "pipeline_logs" in getattr(sanitized_dto, "sanitized_sql", "").lower():
            r = rows[0]
            last_run = r.get("last_run_at") or r.get("max_last_run") or "N/A"
            st = vn_status_translate(r.get("status") or "success")
            model_name = r.get("model_name") or "dwh_internal"
            content = self.render("ETL_FRESHNESS", {
                "last_synced_at": str(last_run),
                "model_name": model_name,
                "status_vietnamese": st,
            })
            return content, False, "ETL_FRESHNESS"

        # 3. Xử lý mẫu Trạng thái Báo cáo (Report Status)
        if any(k in rows[0] for k in ("trang_thai_phe_duyet", "ma_bao_cao")) or "report_status" in intent_val.lower() or "trang_thai" in intent_val.lower():
            if len(rows) == 1:
                r = rows[0]
                st = vn_status_translate(r.get("trang_thai_phe_duyet") or r.get("report_status") or r.get("status") or "approved")
                form_name = r.get("form_name") or r.get("report_title") or "Báo cáo định kỳ"
                form_code = r.get("ma_bao_cao") or r.get("form_code") or r.get("code") or ""
                signoff = r.get("ngay_nop_bao_cao") or r.get("operational_signoff_date") or r.get("created_at") or ""
                content = self.render("REPORT_STATUS", {
                    "form_name": form_name,
                    "entity_name": r.get("ten_phong_ban") or entity_name,
                    "period": period,
                    "status_vietnamese": st,
                    "form_code": form_code,
                    "signoff_date": str(signoff) if signoff else None,
                })
                return content, False, "REPORT_STATUS"
            else:
                reports = []
                for r in rows:
                    st = vn_status_translate(r.get("trang_thai_phe_duyet") or r.get("report_status") or r.get("status") or "approved")
                    reports.append({
                        "code": r.get("ma_bao_cao") or r.get("form_code") or r.get("code") or "BC",
                        "department": r.get("ten_phong_ban") or r.get("department_name") or entity_name,
                        "status": st,
                        "date": str(r.get("ngay_nop_bao_cao") or r.get("created_at") or "-"),
                    })
                content = self.render("REPORT_STATUS_LIST", {
                    "reports": reports,
                    "period": period,
                })
                return content, True, "REPORT_STATUS_LIST"

        # 3b. Xử lý mẫu Bất thường dữ liệu (Data Quality / Anomaly Audit)
        if any(k in rows[0] for k in ("gia_tri_bat_thuong", "anomaly", "bat_thuong")) or "audit" in intent_val.lower() or "anomaly" in intent_val.lower():
            anomalies = []
            for r in rows:
                anomalies.append({
                    "entity": r.get("ten_phong_ban") or r.get("office_name") or entity_name,
                    "metric": r.get("ten_chi_tieu") or r.get("criteria_name") or r.get("ma_chi_tieu") or "Chỉ tiêu",
                    "value": vn_format_num(r.get("gia_tri_bat_thuong") or 0),
                    "status": vn_status_translate(r.get("trang_thai") or "Cần rà soát"),
                })
            content = self.render("DATA_ANOMALY", {
                "anomalies": anomalies,
                "period": period,
            })
            return content, True, "DATA_ANOMALY"

        # 4. Xử lý mẫu Biểu mẫu thu thập (Collection Form)
        if any(k in rows[0] for k in ("ma_bieu_mau", "ten_bieu_mau", "ky_hieu")) or "collection_form" in intent_val.lower() or "bieu_mau" in intent_val.lower():
            forms_list = []
            for r in rows:
                forms_list.append({
                    "code": r.get("ma_bieu_mau") or r.get("code") or r.get("ky_hieu") or "BM",
                    "name": r.get("ten_bieu_mau") or r.get("name") or r.get("form_name") or "Biểu mẫu",
                    "period": r.get("year_code") or period,
                    "agency": r.get("department_name") or entity_name,
                })
            content = self.render("COLLECTION_FORM", {
                "forms": forms_list,
                "period": period,
            })
            return content, True, "COLLECTION_FORM"

        # 5. Xử lý mẫu Phân công nhiệm vụ (User Mission)
        if any(k in rows[0] for k in ("ten_nhiem_vu", "ten_can_bo", "so_chi_tieu_hoan_thanh")) or "mission" in intent_val.lower() or "nhiem_vu" in intent_val.lower():
            missions_list = []
            for r in rows:
                missions_list.append({
                    "assignee": r.get("ten_can_bo") or r.get("full_name") or r.get("assignee") or "Cán bộ phụ trách",
                    "task": r.get("ten_nhiem_vu") or r.get("task_name") or metric_name,
                    "office": r.get("ten_phong_ban") or r.get("office_name") or "-",
                    "status": vn_status_translate(r.get("status") or "Đang thực hiện"),
                })
            content = self.render("USER_MISSION", {
                "missions": missions_list,
            })
            return content, True, "USER_MISSION"

        # 6. Xử lý mẫu So sánh thời gian (Temporal YoY/MoM Comparison)
        # TH1: Kết quả 1 dòng chứa các cột so sánh chuỗi thời gian (LAG / YoY từ Mod 05)
        if len(rows) == 1 and any(k in rows[0] for k in ("ty_le_tang_truong_pct", "tong_nam_truoc", "bien_dong_tuyet_doi")):
            r = rows[0]
            y2 = str(r.get("year") or period)
            y1 = str(int(y2) - 1) if y2.isdigit() else "kỳ trước"
            v2 = float(r.get("tong_gia_tri") or r.get("gia_tri") or 0)
            v1_raw = r.get("tong_nam_truoc")
            v1 = float(v1_raw) if v1_raw is not None else 0.0
            
            delta_raw = r.get("bien_dong_tuyet_doi")
            delta = float(delta_raw) if delta_raw is not None else (v2 - v1)
            delta_abs = abs(delta)
            delta_dir = "tăng" if delta > 0 else ("giảm" if delta < 0 else "không đổi so với")
            delta_sign = "+" if delta > 0 else ("-" if delta < 0 else "")

            growth_pct_raw = r.get("ty_le_tang_truong_pct")
            if growth_pct_raw is not None:
                try:
                    gp_float = float(growth_pct_raw)
                    sign = "+" if gp_float > 0 else ""
                    growth_text = f"tăng {sign}{gp_float:.1f}%" if gp_float >= 0 else f"giảm {gp_float:.1f}%"
                    small_note = f"Số liệu kỳ gốc nhỏ ({v1}), tỷ lệ biến động {growth_text} có thể mang tính đột biến toán học." if (0 < v1 < 5) else None
                except (ValueError, TypeError):
                    gp_float, growth_text, small_note = safe_percentage(v2, v1)
            else:
                gp_float, growth_text, small_note = safe_percentage(v2, v1)

            content = self.render("TEMPORAL_COMPARISON", {
                "metric_name": metric_name,
                "period_1": y1,
                "period_2": y2,
                "val_1_formatted": vn_format_num(v1),
                "val_2_formatted": vn_format_num(v2),
                "unit": unit,
                "delta_direction": delta_dir,
                "delta_abs_formatted": vn_format_num(delta_abs),
                "delta_sign": delta_sign,
                "growth_pct_text": growth_text,
                "small_base_note": small_note,
            })
            return content, True, "TEMPORAL_COMPARISON"

        # TH2: Nhận diện khi có 2 dòng chứa cột year / report_period
        if len(rows) == 2 and any("year" in k for k in rows[0].keys()):
            r1, r2 = rows[0], rows[1]
            # Sắp xếp theo năm tăng dần
            y1 = str(r1.get("year") or "2024")
            y2 = str(r2.get("year") or "2025")
            if y1 > y2:
                r1, r2 = r2, r1
                y1, y2 = y2, y1
            
            # Trích xuất giá trị số
            val_col = next((k for k in r1.keys() if k not in ("year", "period", "tenant_code")), None)
            if val_col:
                try:
                    v1 = float(r1[val_col] or 0)
                    v2 = float(r2[val_col] or 0)
                    delta = v2 - v1
                    delta_abs = abs(delta)
                    delta_dir = "tăng" if delta > 0 else ("giảm" if delta < 0 else "không đổi so với")
                    delta_sign = "+" if delta > 0 else ("-" if delta < 0 else "")
                    
                    growth_pct, growth_text, small_note = safe_percentage(v2, v1)
                    
                    content = self.render("TEMPORAL_COMPARISON", {
                        "metric_name": metric_name,
                        "period_1": y1,
                        "period_2": y2,
                        "val_1_formatted": vn_format_num(v1),
                        "val_2_formatted": vn_format_num(v2),
                        "unit": unit,
                        "delta_direction": delta_dir,
                        "delta_abs_formatted": vn_format_num(delta_abs),
                        "delta_sign": delta_sign,
                        "growth_pct_text": growth_text,
                        "small_base_note": small_note,
                    })
                    return content, True, "TEMPORAL_COMPARISON"
                except (ValueError, TypeError):
                    pass

        # 7. Xử lý mẫu Tỷ trọng bộ phận so với toàn thể (Part to Whole Ratio)
        if any(k in rows[0] for k in ("ty_trong_pct", "ty_trong", "tong_so_toan_tinh", "share_pct")):
            r0 = rows[0]
            share_val = r0.get("ty_trong_pct") or r0.get("ty_trong") or r0.get("share_pct") or 0
            tot_val = r0.get("tong_so_toan_tinh") or r0.get("tong_so") or 0
            ent_name = r0.get("ten_thanh_phan") or r0.get("ten_don_vi") or entity_name
            ent_val = r0.get("gia_tri_thanh_phan") or r0.get("tong_gia_tri") or 0
            content = self.render("PART_TO_WHOLE", {
                "period": period,
                "entity_name": ent_name,
                "share_pct": vn_format_num(share_val),
                "total_val_formatted": vn_format_num(tot_val),
                "entity_val_formatted": vn_format_num(ent_val),
                "unit": unit,
            })
            return content, False, "PART_TO_WHOLE"

        # 8. Xử lý mẫu Xếp hạng Top-K (Ranking Top-K) hoặc Phân rã danh mục (Breakdown List)
        # Hỗ trợ nhận diện các cột tên chuẩn công vụ và cột giá trị
        name_candidates = (
            "ten_don_vi", "ten_thanh_phan", "ten_chi_tieu", "ten_co_quan",
            "ten_phong_ban", "department_name", "office_name", "name", "don_vi"
        )
        val_candidates = (
            "tong_gia_tri", "gia_tri_thanh_phan", "tong_so", "gia_tri",
            "value", "val", "so_luong", "kinh_phi", "tong_nam_nay"
        )
        if 2 <= len(rows) <= 50:
            name_col = next((k for k in name_candidates if k in rows[0]), None)
            val_col = next((k for k in val_candidates if k in rows[0]), None)
            if not val_col:
                val_col = next((k for k in rows[0].keys() if k != name_col and not k.endswith("_id") and not k.endswith("_code") and k not in ("year", "period", "rank_pos", "khoang_bien_do")), None)

            if name_col and val_col:
                try:
                    items = []
                    for r in rows:
                        val_num = float(r[val_col] or 0) if r.get(val_col) is not None else 0.0
                        items.append({
                            "name": r[name_col] or "Chỉ tiêu",
                            "val_num": val_num,
                            "value_formatted": vn_format_num(val_num),
                        })

                    # Cưỡng chế điều kiện chọn template (BUG-001 Fix):
                    # Chỉ chọn RANKING_TOP_K khi archetype thực sự là RANKING hoặc câu hỏi chứa từ khóa xếp hạng/top
                    dag_archetype = getattr(router_output, "dag_archetype", None) or getattr(router_output, "archetype", None)
                    prompt_text = (getattr(router_output, "raw_prompt", "") or getattr(router_output, "query_sanitized", "") or "").lower()
                    is_ranking_request = (
                        dag_archetype in ("RANKING_TOP_K", "RANKING")
                        or any(k in prompt_text for k in ["xếp hạng", "top", "cao nhất", "thấp nhất", "dẫn đầu"])
                    )

                    if is_ranking_request:
                        items.sort(key=lambda x: x["val_num"], reverse=True)
                        spread_formatted = None
                        if len(items) >= 2:
                            spread = abs(items[0]["val_num"] - items[-1]["val_num"])
                            spread_formatted = vn_format_num(spread)

                        content = self.render("RANKING_TOP_K", {
                            "items": items,
                            "metric_name": metric_name,
                            "period": period,
                            "unit": unit,
                            "spread_formatted": spread_formatted,
                        })
                        return content, True, "RANKING_TOP_K"
                    else:
                        # Mẫu phân rã danh mục chỉ tiêu thành phần BREAKDOWN_LIST
                        content = self.render("BREAKDOWN_LIST", {
                            "items": items,
                            "period": period,
                            "entity_name": entity_name,
                            "unit": unit,
                        })
                        return content, True, "BREAKDOWN_LIST"
                except (ValueError, TypeError):
                    pass

        # 9. Xử lý mẫu Chỉ tiêu Đơn lẻ (Direct Metric)
        if len(rows) == 1:
            r = rows[0]
            val_col = next((k for k in val_candidates if k in r), None)
            if not val_col:
                val_keys = [k for k in r.keys() if k not in ("tenant_code", "year", "period", "office_id", "department_code")]
                val_col = val_keys[0] if val_keys else None
            
            if val_col:
                raw_val = r[val_col]
                formatted_val = vn_format_num(raw_val)
                row_entity = next((r.get(c) for c in name_candidates if r.get(c)), entity_name)
                content = self.render("DIRECT_METRIC", {
                    "period": period,
                    "entity_name": row_entity,
                    "metric_name": metric_name,
                    "value_formatted": formatted_val,
                    "unit": unit,
                })
                return content, False, "DIRECT_METRIC"

        # Nếu không khớp mẫu chuẩn nào -> trả về None để LLM Synthesizer đảm nhiệm
        return None
