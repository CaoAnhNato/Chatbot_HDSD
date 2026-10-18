"""
Động cơ Dự phóng Ngôn ngữ Tự nhiên (LLM Synthesizer) cho Module 08.
Sử dụng google/gemini-2.5-flash-lite theo chuẩn BLUF (Bottom Line Up Front) nghiêm ngặt.
Áp dụng cơ chế Safety Buffer Ceiling (max_tokens = 2048) để triệt tiêu nguy cơ cắt cụt văn bản,
kiểm soát độ dài và tính cô đọng tuyệt đối bằng System Prompt với Negative Constraints.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from IPGov_Chatbot.config import settings
from IPGov_Chatbot.core.llm_gateway import get_llm_gateway
from IPGov_Chatbot.modules.mod08_response.jinja_slot_engine import vn_format_num

logger = logging.getLogger("ipgov.mod08.llm_synthesizer")

BLUF_SYSTEM_PROMPT = """Bạn là Trợ lý Tổng hợp Dữ liệu Hành chính Công vụ Tỉnh Lâm Đồng (IPGov Synthesizer).
Nhiệm vụ của bạn là đọc kết quả truy vấn CSDL kho dữ liệu (DWH) và trả lời người dùng theo chuẩn BLUF (Bottom Line Up Front) nghiêm ngặt nhất.

CÁC RÀNG BUỘC PHỦ ĐỊNH TUYỆT ĐỐI (NEGATIVE CONSTRAINTS):
1. [CẤM CHÀO HỎI]: Tuyệt đối KHÔNG sử dụng lời chào, lời cảm ơn hay xưng hô xã giao ("Xin chào", "Chào bạn", "Kính gửi", "Thưa bạn").
2. [CẤM MỞ ĐẦU RƯỜM RÀ]: Tuyệt đối KHÔNG dùng các câu dẫn nhập như "Dưới đây là kết quả...", "Theo dữ liệu được cung cấp...", "Dựa vào bảng truy vấn...".
3. [CẤM LẶP LẠI CÂU HỎI]: Không viết lại nguyên văn câu hỏi của người dùng.
4. [CẤM ẢO GIÁC]: Chỉ sử dụng các con số, cột, dòng có trong dữ liệu kết quả DWH. Không tự bịa đặt hay suy diễn thêm số liệu ngoài bảng.

CẤU TRÚC PHẢN HỒI BẮT BUỘC (BLUF FORMAT):
1. ĐỐI VỚI TRA CỨU ĐƠN LẺ MỘT CHỈ TIÊU (SINGLE METRIC SNAPSHOT - 1 DÒNG):
Bắt buộc trình bày đầy đủ 5 trường thông tin theo đúng định dạng:
- **Chỉ tiêu:** [Tên chỉ tiêu]
- **Giá trị:** [Số liệu định dạng phân cách hàng nghìn]
- **Đơn vị thực hiện:** [Tên văn phòng / phòng ban, vd: Chi cục]
- **Nhiệm vụ trọng tâm:** [Tên nhiệm vụ, vd: Phát triển nông thôn]
- **Thời điểm báo cáo:** [Ngày báo cáo / phê duyệt dạng DD/MM/YYYY]

2. ĐỐI VỚI DANH SÁCH / BẢNG CHỈ TIÊU (LISTING / INVENTORY - TỪ 2 DÒNG TRỞ LÊN):
Bắt buộc trình bày dưới dạng 1 bảng Markdown tinh gọn với các cột:
`STT | Tên chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm`
Định dạng số bằng dấu chấm phân cách hàng nghìn (ví dụ 1.234.567).
- DÒNG QUAN SÁT (TÙY CHỌN): Tối đa đúng 1 gạch đầu dòng (bullet) nhận xét xu hướng chính (không quá 30 từ). Không viết thêm bất kỳ đoạn văn nào khác.
"""


def _construct_user_prompt(
    user_prompt: str,
    query_result: Any,
    extracted_entities: Dict[str, Any],
) -> str:
    """Tạo nội dung User Prompt bao gồm câu hỏi gốc và dữ liệu DWH đã cắt lát (Data Slicing)."""
    rows = getattr(query_result, "rows", [])
    row_count = getattr(query_result, "row_count", len(rows))
    
    # Cắt lát dữ liệu tối đa 10 dòng tiêu biểu để tiết kiệm token
    sliced_rows = rows[:10]
    
    # Chuẩn bị thông tin tóm tắt
    data_summary = {
        "total_records_in_dwh": row_count,
        "displayed_records_count": len(sliced_rows),
        "data_slice": sliced_rows,
        "extracted_context": {
            "period": extracted_entities.get("year") or extracted_entities.get("period"),
            "department": extracted_entities.get("department_name") or extracted_entities.get("department"),
            "metric": extracted_entities.get("metric_name") or extracted_entities.get("criteria_name"),
            "unit": extracted_entities.get("unit"),
        }
    }
    
    prompt = (
        f"CÂU HỎI NGƯỜI DÙNG: \"{user_prompt}\"\n\n"
        f"KẾT QUẢ DỮ LIỆU TỪ KHO DWH:\n"
        f"```json\n{json.dumps(data_summary, ensure_ascii=False, indent=2)}\n```\n\n"
        f"Hãy tổng hợp câu trả lời theo đúng chuẩn BLUF: nếu là 1 chỉ tiêu đơn lẻ thì trình bày 5 gạch đầu dòng (Chỉ tiêu, Giá trị, Đơn vị thực hiện, Nhiệm vụ trọng tâm, Thời điểm báo cáo). Nếu là danh sách >= 2 dòng thì trình bày Bảng Markdown 5 cột (STT, Tên chỉ tiêu, Giá trị mới nhất, Đơn vị thực hiện, Nhiệm vụ trọng tâm)."
    )
    return prompt


def _render_offline_fallback(
    query_result: Any,
    user_prompt: str,
    extracted_entities: Dict[str, Any],
) -> Tuple[str, bool]:
    """Cơ chế Fallback ngoại tuyến tất định khi LLM API gặp sự cố hoặc offline."""
    rows = getattr(query_result, "rows", [])
    if not rows:
        return "Không tìm thấy bản ghi số liệu đã được phê duyệt trong kho DWH.", False

    first_row = rows[0]

    # Kiểm tra xem có cấu trúc fact chỉ tiêu với đơn vị thực hiện và nhiệm vụ hay không
    has_fact_context = any(k in first_row for k in ["ten_chi_tieu", "ten_van_phong", "ten_nhiem_vu", "gia_tri_moi_nhat", "ngay_bao_cao"]) or "office_name" in first_row or "mission_name" in first_row

    if len(rows) == 1 and has_fact_context:
        crit_name = first_row.get("ten_chi_tieu") or first_row.get("name") or extracted_entities.get("metric_name") or "Chỉ tiêu"
        val = first_row.get("gia_tri") or first_row.get("gia_tri_moi_nhat") or first_row.get("value") or first_row.get("tong_gia_tri")
        if val is None or (isinstance(val, str) and val.strip() in ("", "-", "None", "null", "N/A")):
            fmt_val = "Chưa có số liệu phê duyệt (-)"
        else:
            fmt_val = vn_format_num(val)
        office = first_row.get("ten_van_phong") or first_row.get("office_name") or "Toàn tỉnh / Cơ quan chủ quản"
        mission = first_row.get("ten_nhiem_vu") or first_row.get("mission_name") or "Theo dõi chung"
        raw_date = first_row.get("ngay_bao_cao") or first_row.get("ngay_bao_cao_moi_nhat") or first_row.get("report_date") or ""
        date_str = str(raw_date)[:10] if raw_date else "-"
        if "-" in date_str and len(date_str) == 10:
            parts = date_str.split("-")
            date_str = f"{parts[2]}/{parts[1]}/{parts[0]}"

        content = (
            f"- **Chỉ tiêu:** {crit_name}\n"
            f"- **Giá trị:** {fmt_val}\n"
            f"- **Đơn vị thực hiện:** {office}\n"
            f"- **Nhiệm vụ trọng tâm:** {mission}\n"
            f"- **Thời điểm báo cáo:** {date_str}"
        )
        return content, False

    # Nếu có nhiều dòng và là bảng chỉ tiêu
    if len(rows) >= 2 and has_fact_context:
        table_lines = [
            "| STT | Tên chỉ tiêu | Giá trị mới nhất | Đơn vị thực hiện | Nhiệm vụ trọng tâm |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for idx, r in enumerate(rows[:20], 1):
            name = r.get("ten_chi_tieu") or r.get("name") or "-"
            val = r.get("gia_tri") or r.get("gia_tri_moi_nhat") or r.get("value") or r.get("tong_gia_tri") or "-"
            office = r.get("ten_van_phong") or r.get("office_name") or "Cơ quan chủ quản"
            mission = r.get("ten_nhiem_vu") or r.get("mission_name") or "Theo dõi chung"
            table_lines.append(f"| {idx} | {name} | {vn_format_num(val)} | {office} | {mission} |")

        table_md = "\n".join(table_lines)
        return f"Danh sách số liệu chỉ tiêu đã phê duyệt ({len(rows)} bản ghi):\n\n{table_md}", True

    # Fallback mặc định cho các bảng khác (province, deparment, etc.)
    cols = [k for k in first_row.keys() if not k.endswith("_id")]
    if not cols:
        cols = list(first_row.keys())

    period = extracted_entities.get("year") or extracted_entities.get("period") or "2026"
    metric = extracted_entities.get("metric_name") or extracted_entities.get("criteria_name") or "Chỉ tiêu"

    if len(rows) == 1:
        val_str = ", ".join(f"{c}: {vn_format_num(first_row[c])}" for c in cols)
        content = f"Số liệu báo cáo năm {period} ghi nhận {metric}: **{val_str}**."
        return content, False

    header = "| " + " | ".join(cols) + " |"
    divider = "| " + " | ".join([":---" for _ in cols]) + " |"
    table_lines = [header, divider]
    for r in rows[:15]:
        line = "| " + " | ".join(str(vn_format_num(r.get(c, "-"))) for c in cols) + " |"
        table_lines.append(line)

    table_md = "\n".join(table_lines)
    content = (
        f"Kết quả tra cứu {metric} năm {period} ({len(rows)} bản ghi):\n\n"
        f"{table_md}"
    )
    return content, True


class LLMSynthesizer:
    """
    Bộ tổng hợp ngôn ngữ tự nhiên sử dụng google/gemini-2.5-flash-lite.
    """

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or getattr(settings, "GEMINI_MODEL_NAME", "google/gemini-2.5-flash-lite")
        # Safety Buffer Ceiling 2048 tokens đảm bảo không bị cắt cụt bảng Markdown
        self.max_tokens = 2048
        self.temperature = 0.0

    async def synthesize_async(
        self,
        query_result: Any,
        user_prompt: str,
        extracted_entities: Dict[str, Any],
        trace_id: str = "",
    ) -> Tuple[str, bool, int]:
        """
        Tổng hợp câu trả lời bất đồng bộ qua LLMGateway.
        Trả về: (content, table_rendered, tokens_used)
        """
        rows = getattr(query_result, "rows", [])
        if not rows:
            return "Không tìm thấy bản ghi số liệu đã được phê duyệt trong kho DWH.", False, 0

        prompt = _construct_user_prompt(user_prompt, query_result, extracted_entities)

        try:
            gw = get_llm_gateway()
            response_text = await gw.call_chat(
                prompt=prompt,
                system_prompt=BLUF_SYSTEM_PROMPT,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            cleaned = response_text.strip()
            table_rendered = "|" in cleaned and "-|-" in cleaned or "\n|" in cleaned
            # Ước lượng tokens hoặc lấy từ metadata log
            tokens_used = max(len(prompt.split()) + len(cleaned.split()), 50)
            return cleaned, table_rendered, tokens_used
        except Exception as e:
            logger.warning(f"[{trace_id}] LLM Synthesizer gọi thất bại ({e}). Áp dụng Fallback tất định.")
            content, table_rendered = _render_offline_fallback(query_result, user_prompt, extracted_entities)
            return content, table_rendered, 0

    def synthesize_sync(
        self,
        query_result: Any,
        user_prompt: str,
        extracted_entities: Dict[str, Any],
        trace_id: str = "",
    ) -> Tuple[str, bool, int]:
        """
        Tổng hợp câu trả lời đồng bộ qua LLMGateway.
        Trả về: (content, table_rendered, tokens_used)
        """
        rows = getattr(query_result, "rows", [])
        if not rows:
            return "Không tìm thấy bản ghi số liệu đã được phê duyệt trong kho DWH.", False, 0

        prompt = _construct_user_prompt(user_prompt, query_result, extracted_entities)

        try:
            gw = get_llm_gateway()
            response_text = gw.call_chat_sync(
                prompt=prompt,
                system_prompt=BLUF_SYSTEM_PROMPT,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            cleaned = response_text.strip()
            table_rendered = "|" in cleaned and "-|-" in cleaned or "\n|" in cleaned
            tokens_used = max(len(prompt.split()) + len(cleaned.split()), 50)
            return cleaned, table_rendered, tokens_used
        except Exception as e:
            logger.warning(f"[{trace_id}] LLM Synthesizer (sync) thất bại ({e}). Áp dụng Fallback tất định.")
            content, table_rendered = _render_offline_fallback(query_result, user_prompt, extracted_entities)
            return content, table_rendered, 0
