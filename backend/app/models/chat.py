from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from app.models.chunk import DocumentChunk


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: 'user', 'assistant', 'system'")
    content: str = Field(..., description="Text content")


class ChatRequest(BaseModel):
    query: str = Field(..., description="Câu hỏi hoặc yêu cầu của người dùng")
    session_id: Optional[str] = Field(None, description="Session ID cho multi-turn conversation")
    history: List[ChatMessage] = Field(default_factory=list, description="Lịch sử hội thoại")
    top_k: int = Field(3, description="Số lượng chunks truy xuất từ Vector Store")
    stream: bool = Field(False, description="Bật chế độ streaming response")
    collection: Optional[str] = Field(None, description="ChromaDB collection name")
    role: Optional[str] = Field("phuong", description="Phân hệ: 'phuong' hoặc 'dn'")


class QuickActionChip(BaseModel):
    id: str
    label: str
    query_text: str


class ContactSupportInfo(BaseModel):
    title: str = "THÔNG TIN LIÊN HỆ HỖ TRỢ KỸ THUẬT"
    working_hours: str = "Thứ 2 - Thứ 6 (Sáng: 07h30 – 11h30, Chiều: 13h00 – 17h00)"
    hotlines: List[str] = ["028 3535 2524"]
    zalo: Optional[str] = None

    @classmethod
    def for_phuong(cls) -> "ContactSupportInfo":
        return cls(
            title="THÔNG TIN LIÊN HỆ HỖ TRỢ KỸ THUẬT (PHƯỜNG/XÃ)",
            working_hours="Thứ 2 - Thứ 6 (Sáng: 07h30 – 11h30, Chiều: 13h00 – 17h00)",
            hotlines=["028 3535 2524"],
            zalo=None
        )

    @classmethod
    def for_dn(cls) -> "ContactSupportInfo":
        return cls(
            title="THÔNG TIN LIÊN HỆ HỖ TRỢ KỸ THUẬT (DOANH NGHIỆP)",
            working_hours="Thứ 2 - Thứ 6 (Sáng: 08h00 – 11h00, Chiều: 13h00 – 17h00)",
            hotlines=["028 3535 2523", "028 3535 2524"],
            zalo="0967 862 523"
        )


class ChatResponse(BaseModel):
    session_id: str
    answer: str = Field(..., description="Rich Markdown câu trả lời từ Qwen AI")
    source_chunks: List[DocumentChunk] = Field(default_factory=list, description="Chunks đã sử dụng")
    images: List[str] = Field(default_factory=list, description="Danh sách URL ảnh liên quan")
    youtube_links: List[str] = Field(default_factory=list, description="Danh sách link YouTube có timestamp")
    quick_action_chips: Optional[List[QuickActionChip]] = Field(None, description="Gợi ý chọn khi câu hỏi mơ hồ")
    contact_support: Optional[ContactSupportInfo] = Field(None, description="Thông tin liên hệ khi gặp sự cố")
    intent: Optional[str] = Field(None, description="Ý định phân loại (knowledge, chitchat, error, ambiguity)")
