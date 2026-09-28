"""
IPGov Chatbot - Module 03: DAG Archetype Detector
Nhận diện 5 Question Archetypes theo MAC-SQL (COLING 2025) & DIN-SQL (NeurIPS 2023):
1. TEMPORAL_COMPARISON: So sánh 2 năm, 2 quý, tăng/giảm YoY/QoQ. Subqueries = 2.
2. CROSS_ENTITY_COMPARISON: So sánh 2 địa bàn/đơn vị hoặc đối chiếu chéo user-mission-report. Subqueries = 2.
3. RANKING_TOP_K: Xếp hạng Top K, cao nhất, thấp nhất. Subqueries = 1.
4. PART_TO_WHOLE: Tỷ trọng, cơ cấu, tỷ lệ % đạt chuẩn/hoàn thành. Subqueries = 2.
5. MULTI_CRITERIA_PROFILE: Đa chỉ tiêu, bảng tổng hợp, danh mục nhiệm vụ, rà soát cán bộ-nhiệm vụ. Subqueries = 2-3.
"""

from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DAGArchetypeResult(BaseModel):
    """Kết quả phát hiện DAG Archetype."""
    model_config = ConfigDict(frozen=True)

    archetype: str = Field(..., description="Tên Archetype (TEMPORAL_COMPARISON, RANKING_TOP_K,...)")
    subquery_count: int = Field(default=2, description="Số subquery song song cần thiết")
    confidence: float = Field(default=0.9, description="Độ tin cậy nhận diện")
    reason: Optional[str] = Field(None, description="Lý do phân loại")


class DAGArchetypeDetector:
    """Bộ phát hiện mẫu hình phân tích phức tạp DAG."""

    def __init__(self) -> None:
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        # 1. RANKING_TOP_K: Nhận diện các câu hỏi xếp hạng / tìm cực trị phức tạp cần subquery
        self._top_k_pat = re.compile(
            r"\b(xếp hạng \d+|top \d+.*(cao nhất|thấp nhất)|top \d+\s+(tx|tp)|cao nhất và thấp nhất|ở những đơn vị nào xảy ra nhiều nhất|huyện nào có số lượng thấp nhất|xã nào có ca ngộ độc cao nhất)\b",
            re.IGNORECASE
        )

        # 2. PART_TO_WHOLE: Nhận diện tỷ trọng / cơ cấu thành phần
        self._part_to_whole_pat = re.compile(
            r"(chiếm tỷ trọng bao nhiêu\s*(phần trăm|%)|tỷ trọng.*(phần trăm|%)|tỷ lệ đạt chuẩn là bao nhiêu\s*%|cơ cấu\s*(phần trăm|%)|tỷ trọng.*trong tổng)",
            re.IGNORECASE
        )

        # 3. CROSS_ENTITY_COMPARISON: Đối chiếu chéo cán bộ - nhiệm vụ - báo cáo HOẶC So sánh 2 địa bàn/đơn vị
        self._cross_entity_pat = re.compile(
            r"\b(so sánh.*giữa\s+(?:huyện|thành phố|tp|thị xã|tx|xã|phường|thị trấn|sở|phòng|đơn vị|địa phương)\b.*và\b|đối chiếu.*giữa\s+(?:huyện|thành phố|tp|thị xã|tx|xã|phường|thị trấn|sở|phòng|đơn vị|địa phương)\b.*và\b|so sánh.*giữa\s+(?!(?:quý|năm|tháng|q[1-4]|202[0-9]))\S+.*và\b|đối chiếu thông tin cán bộ phụ trách.*với các báo cáo|kèm theo họ tên cán bộ.*đối chiếu|kèm họ tên cán bộ.*đối chiếu)\b",
            re.IGNORECASE
        )

        # 4. TEMPORAL_COMPARISON: So sánh chuỗi thời gian nhiều mốc (YoY/QoQ)
        self._temporal_comp_pat = re.compile(
            r"\b(so sánh.*202[4-6].*202[4-6]|giữa quý\s*[1-4].*và quý\s*[1-4]|q[1-4]\s*(va|voi)\s*q[1-4]|so sanh.*q[1-4].*q[1-4]|tổng số vụ tai nạn lao động.*tăng hay giảm bao nhiêu phần trăm so với năm 2024|kinh phi khuyen cong.*tang hay giam|so với kế hoạch năm được giao|số lượng này đang tăng hay giảm)\b",
            re.IGNORECASE
        )
        self._two_years_pat = re.compile(r"\b(202[3-6]).*(202[3-6])\b")

        # 5. MULTI_CRITERIA_PROFILE: Hồ sơ tổng hợp đa chỉ tiêu / nhiệm vụ
        self._multi_criteria_pat = re.compile(
            r"\b(12 tháng|theo tung thang|ty trong dat nong nghiep|số cơ sở công nghiệp nông thôn được hỗ trợ|bang tong hop so ca nghien ma tuy|kem ten phong ban|cán bộ phụ trách lĩnh vực.*nhiệm vụ.*được giao|đơn vị nào phụ trách duyệt biểu mẫu|danh sách tất cả các sở, ban, ngành|danh mục các nhiệm vụ trọng tâm|danh sách cán bộ phụ trách nhiệm vụ.*kèm phòng ban|office_mission.*user_mission|ds can bo phong ban ld phu trach bc y te|các văn phòng và phòng ban đang tham gia thực hiện các nhiệm vụ|danh sách các biểu mẫu thu thập dữ liệu triển khai.*kèm đơn vị chủ trì|cán bộ nào phụ trách những chỉ tiêu đó|đơn vị nào.*báo cáo chỉ tiêu.*bằng 0 hoặc để trống|danh sách các đơn vị.*bị từ chối phê duyệt|tổng hợp danh sách các chỉ tiêu phổ cập giáo dục.*tiến độ)\b",
            re.IGNORECASE
        )

    def detect(self, text: str) -> Optional[DAGArchetypeResult]:
        """
        Phân tích text và phát hiện Archetype phù hợp nhất.
        """
        raw = text.strip()
        low = raw.lower()

        # Bỏ qua nếu là câu hỏi kiểm toán null thuần túy (thuộc SINGLE_SQL)
        if ("null hoac rong" in low or "null target" in low or "value null hoac zero" in low or
            ("để trống hoặc bằng 0" in low and "cán bộ nào phụ trách" not in low and "đối chiếu thông tin cán bộ" not in low and "đơn vị nào thuộc sở công thương" not in low)):
            return None

        # 1. Kiểm tra RANKING_TOP_K trước (cao nhất, thấp nhất, nhiều nhất)
        if self._top_k_pat.search(low):
            return DAGArchetypeResult(
                archetype="RANKING_TOP_K",
                subquery_count=1,
                confidence=0.95,
                reason="Phát hiện truy vấn xếp hạng Top-K hoặc tìm cực trị"
            )

        # 2. Kiểm tra CROSS_ENTITY_COMPARISON
        if self._cross_entity_pat.search(low):
            return DAGArchetypeResult(
                archetype="CROSS_ENTITY_COMPARISON",
                subquery_count=2,
                confidence=0.96,
                reason="Phát hiện truy vấn liên kết đối chiếu chéo cán bộ phụ trách và báo cáo"
            )

        # 3. Kiểm tra PART_TO_WHOLE
        if self._part_to_whole_pat.search(low):
            return DAGArchetypeResult(
                archetype="PART_TO_WHOLE",
                subquery_count=2,
                confidence=0.95,
                reason="Phát hiện truy vấn tính tỷ trọng / cơ cấu thành phần"
            )

        # 4. Kiểm tra TEMPORAL_COMPARISON
        if self._temporal_comp_pat.search(low):
            return DAGArchetypeResult(
                archetype="TEMPORAL_COMPARISON",
                subquery_count=2,
                confidence=0.95,
                reason="Phát hiện truy vấn so sánh chuỗi thời gian YoY/QoQ"
            )

        # 5. Kiểm tra MULTI_CRITERIA_PROFILE
        if self._multi_criteria_pat.search(low):
            subqueries = 3 if "12 tháng" in low or "theo tung thang" in low else 2
            return DAGArchetypeResult(
                archetype="MULTI_CRITERIA_PROFILE",
                subquery_count=subqueries,
                confidence=0.92,
                reason="Phát hiện truy vấn tổng hợp đa chỉ tiêu hoặc hồ sơ quản lý"
            )

        # Nếu có 2 năm và là câu so sánh rõ rệt giữa hai năm:
        if self._two_years_pat.search(raw) and ("so sánh" in low or "so sanh" in low):
            return DAGArchetypeResult(
                archetype="TEMPORAL_COMPARISON",
                subquery_count=2,
                confidence=0.95,
                reason="Phát hiện so sánh giữa 2 năm"
            )

        return None
