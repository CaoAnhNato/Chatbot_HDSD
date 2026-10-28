"""
Module: IPGov_Chatbot/schemas/user_context.py
Chức năng: Hợp đồng dữ liệu ngữ cảnh định danh và phân quyền HBAC của người dùng (UserSecurityContextDTO).
Tuân thủ chuẩn Arc42, IEEE Std 1016-2009 và ipgov-coding-rules.md.
"""

from typing import Any, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


class UserSecurityContextDTO(BaseModel):
    """
    Hợp đồng dữ liệu ngữ cảnh an ninh và thẩm quyền của người dùng (HBAC Context).
    Được trích xuất trực tiếp từ Bearer JWT tại API Gateway.
    """
    model_config = ConfigDict(frozen=False, protected_namespaces=())

    user_id: str = Field(default="default_user", description="Định danh duy nhất của người dùng trong hệ thống")
    username: str = Field(default="user", description="Tên đăng nhập hoặc chức danh công vụ")
    tenant_code: str = Field(default="68", description="Mã tỉnh/thành phố trực thuộc Trung ương (e.g. '68': Lâm Đồng, '79': TP.HCM)")
    department_code: Optional[str] = Field(None, description="Mã Sở/Ban/Ngành hoặc UBND huyện (e.g. '68-1-02', '79-1-01')")
    office_id: Optional[str] = Field(None, description="Định danh phòng ban chuyên môn cấp 2 (UUID hoặc chuỗi định danh)")
    name: Optional[str] = Field(default=None, description="Họ và tên hoặc tên hiển thị của tài khoản")
    user_name: Optional[str] = Field(default=None, description="Tên người dùng (alias cho name)")
    schema: str = Field(default="dwh_internal", description="Schema kho dữ liệu hiện hành ('dwh_internal' hoặc 'dwh_public')")
    assigned_mission_ids: List[str] = Field(default_factory=list, description="Danh sách UUID nhiệm vụ được phân công")
    assigned_mission_names: List[str] = Field(default_factory=list, description="Danh sách tên nhiệm vụ được phân công")
    is_unrestricted: bool = Field(default=False, description="True nếu là tài khoản Lãnh đạo hoặc được miễn trừ kiểm tra nhiệm vụ")
    role_level: int = Field(
        default=1,
        ge=0,
        le=4,
        description="Cấp độ thẩm quyền (4: Lãnh đạo Toàn quyền, 3: Quản trị Đa nhiệm vụ, 2: Chuyên trách, 1: Đơn nhiệm, 0: Giới hạn)"
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

    @field_validator("schema", mode="before")
    @classmethod
    def sanitize_schema(cls, v: Any) -> str:
        clean_v = str(v or "").strip().lower()
        return "dwh_public" if clean_v == "dwh_public" else "dwh_internal"

    def model_post_init(self, __context: Any) -> None:
        """Đồng bộ alias name/user_name, chuẩn hóa schema và kích hoạt is_unrestricted cho Lãnh đạo."""
        if getattr(self, "schema", None) != "dwh_public":
            self.schema = "dwh_internal"

        if self.user_name and not self.name:
            self.name = self.user_name
        elif self.name and not self.user_name:
            self.user_name = self.name

        display_name = (self.name or self.user_name or "").strip()
        if display_name == "Lãnh đạo" or self.username == "boss" or (self.role_level == 4 and (display_name == "Lãnh đạo" or self.is_unrestricted)):
            self.is_unrestricted = True

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

