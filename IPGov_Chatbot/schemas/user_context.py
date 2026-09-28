"""
Module: IPGov_Chatbot/schemas/user_context.py
Chức năng: Hợp đồng dữ liệu ngữ cảnh định danh và phân quyền HBAC của người dùng (UserSecurityContextDTO).
Tuân thủ chuẩn Arc42, IEEE Std 1016-2009 và ipgov-coding-rules.md.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class UserSecurityContextDTO(BaseModel):
    """
    Hợp đồng dữ liệu ngữ cảnh an ninh và thẩm quyền của người dùng (HBAC Context).
    Được trích xuất trực tiếp từ Bearer JWT tại API Gateway.
    """
    model_config = ConfigDict(frozen=True)

    user_id: str = Field(..., description="Định danh duy nhất của người dùng trong hệ thống")
    username: str = Field(..., description="Tên đăng nhập hoặc chức danh công vụ")
    tenant_code: str = Field(..., description="Mã tỉnh/thành phố trực thuộc Trung ương (e.g. '68': Lâm Đồng, '79': TP.HCM)")
    department_code: Optional[str] = Field(None, description="Mã Sở/Ban/Ngành hoặc UBND huyện (e.g. '68-1-02', '79-1-01')")
    office_id: Optional[str] = Field(None, description="Định danh phòng ban chuyên môn cấp 2 (UUID hoặc chuỗi định danh)")
    role_level: int = Field(
        ...,
        ge=0,
        le=3,
        description="Cấp độ thẩm quyền: 0: Cấp Tỉnh/TP, 1: Cấp Sở/Huyện, 2: Cấp Phòng ban, 3: Công dân/Public"
    )

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
