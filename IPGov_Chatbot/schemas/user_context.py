"""
Module: IPGov_Chatbot/schemas/user_context.py
Chức năng: Hợp đồng dữ liệu ngữ cảnh định danh và phân quyền HBAC của người dùng (UserSecurityContextDTO).
Tuân thủ chuẩn Arc42, IEEE Std 1016-2009 và ipgov-coding-rules.md.
"""

from typing import List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


class UserSecurityContextDTO(BaseModel):
    """
    Hợp đồng dữ liệu ngữ cảnh an ninh và thẩm quyền của người dùng (HBAC Context).
    Được trích xuất trực tiếp từ Bearer JWT tại API Gateway.
    """
    model_config = ConfigDict(frozen=False)

    user_id: str = Field(default="default_user", description="Định danh duy nhất của người dùng trong hệ thống")
    username: str = Field(default="user", description="Tên đăng nhập hoặc chức danh công vụ")
    tenant_code: str = Field(default="68", description="Mã tỉnh/thành phố trực thuộc Trung ương (e.g. '68': Lâm Đồng, '79': TP.HCM)")
    department_code: Optional[str] = Field(None, description="Mã Sở/Ban/Ngành hoặc UBND huyện (e.g. '68-1-02', '79-1-01')")
    office_id: Optional[str] = Field(None, description="Định danh phòng ban chuyên môn cấp 2 (UUID hoặc chuỗi định danh)")
    role_level: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Cấp độ thẩm quyền HBAC (0: Cấp Tỉnh, 1: Cấp Sở, 2: Cấp Phòng, 3: Công dân/Khách)"
    )
    status_filter: Optional[Union[str, List[str]]] = Field(
        default=None,
        description="Trạng thái báo cáo được yêu cầu lọc ('approved', 'draft', 'pending', 'rejected', 'ALL_STATUSES', 'ALL')"
    )
    blocked_draft_access: bool = Field(
        default=False,
        description="True nếu người dùng cấp 3 (Công dân/Khách) bị HBAC chặn quyền xem dữ liệu draft/pending"
    )
    explicit_role_provided: bool = Field(
        default=False,
        description="True nếu role_level được truyền tường minh từ user_context của request"
    )

    def get_status_list(self) -> List[str]:
        """Chuẩn hóa status_filter (str hoặc List[str]) về danh sách chữ thường."""
        if not self.status_filter:
            return []
        raw_items = [self.status_filter] if isinstance(self.status_filter, str) else list(self.status_filter)
        out: List[str] = []
        for item in raw_items:
            val = str(item).strip().lower()
            if not val:
                continue
            if val in ("all", "all_statuses", "*"):
                out.append("all")
            else:
                out.append(val)
        return out

    def get(self, key: str, default=None):
        """Hỗ trợ truy xuất kiểu dict-like tương thích ngược với các node LangGraph."""
        return getattr(self, key, default)

    @property
    def is_province_level(self) -> bool:
        """Kiểm tra có phải thẩm quyền cấp Tỉnh (toàn quyền xem dữ liệu của tỉnh)."""
        return self.role_level == 0

    @property
    def is_department_level(self) -> bool:
        """Kiểm tra có phải thẩm quyền cấp Sở/Ban/Ngành."""
        return self.role_level == 1

    @property
    def is_office_level(self) -> bool:
        """Kiểm tra có phải thẩm quyền cấp Phòng ban chuyên môn trực thuộc."""
        return self.role_level == 2

    @property
    def is_public(self) -> bool:
        """Kiểm tra có phải tài khoản công dân vãng lai chỉ xem dữ liệu công khai."""
        return self.role_level >= 3

