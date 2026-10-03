"""
Module: IPGov_Chatbot/modules/mod01_gateway/context_extractor.py
Chức năng: Trích xuất và xác thực UserSecurityContextDTO từ Bearer JWT Header.
Cung cấp 6 Profiles mẫu phục vụ thử nghiệm phân quyền HBAC Cấp Tỉnh, Cấp Sở, Cấp Phòng.
"""

from typing import Dict, Any, Optional
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO
from IPGov_Chatbot.modules.mod01_gateway.jwt_service import JWTService, DEFAULT_JWT_SECRET


# 6 Profiles chuẩn hóa cho môi trường kiểm thử thực tế CSDL vna_wom_dev
SAMPLE_ROLE_PROFILES: Dict[str, Dict[str, Any]] = {
    "lamdong_province_leader": {
        "user_id": "u_ld_001",
        "username": "lanhdao_ubnd_lamdong",
        "tenant_code": "68",
        "department_code": None,
        "office_id": None,
        "role_level": 0,
        "description": "Lãnh đạo Cấp Tỉnh - UBND Tỉnh Lâm Đồng (Toàn quyền xem dữ liệu Tỉnh)"
    },
    "tphcm_province_leader": {
        "user_id": "u_hcm_001",
        "username": "lanhdao_ubnd_tphcm",
        "tenant_code": "79",
        "department_code": None,
        "office_id": None,
        "role_level": 0,
        "description": "Lãnh đạo Cấp Tỉnh - UBND TP. Hồ Chí Minh"
    },
    "tphcm_so_noivu": {
        "user_id": "u_snv_001",
        "username": "giamdoc_so_noivu_hcm",
        "tenant_code": "79",
        "department_code": "79-1-01",
        "office_id": None,
        "role_level": 1,
        "description": "Cấp Sở/Ngành - Giám đốc Sở Nội Vụ TP.HCM"
    },
    "lamdong_phong_kinhte": {
        "user_id": "u_pkt_001",
        "username": "truongphong_kinhte_lamdong",
        "tenant_code": "68",
        "department_code": "68-1-02",
        "office_id": None,
        "role_level": 2,
        "description": "Cấp Phòng ban chuyên môn - Phòng Kinh tế UBND Tỉnh Lâm Đồng"
    },
    "lamdong_phong_xaydung": {
        "user_id": "u_pxd_001",
        "username": "chuyenvien_xaydung_lamdong",
        "tenant_code": "68",
        "department_code": "68-1-02",
        "office_id": None,
        "role_level": 2,
        "description": "Cấp Phòng ban chuyên môn - Phòng ban xây dựng Lâm Đồng"
    },
    "public_citizen": {
        "user_id": "u_pub_999",
        "username": "congdan_tra_cuu",
        "tenant_code": "68",
        "department_code": None,
        "office_id": None,
        "role_level": 3,
        "description": "Công dân vãng lai tra cứu số liệu công khai (Public Access)"
    }
}


class ContextExtractor:
    """Bộ bóc tách và hợp thức hóa ngữ cảnh an ninh từ HTTP Header."""

    @classmethod
    def extract_from_auth_header(
        cls,
        auth_header: Optional[str],
        secret_key: str = DEFAULT_JWT_SECRET
    ) -> UserSecurityContextDTO:
        """
        Bóc tách Bearer JWT từ Authorization Header, giải mã và trả về UserSecurityContextDTO.
        
        Args:
            auth_header: Chuỗi `Bearer <token>` từ HTTP request.
            secret_key: Khóa ký số bí mật.
            
        Returns:
            UserSecurityContextDTO: Đối tượng định danh phân quyền an toàn.
            
        Raises:
            ValueError: Khi thiếu header, định dạng sai, hoặc token không hợp lệ.
        """
        if not auth_header:
            raise ValueError("Thiếu Authorization Header. Bắt buộc phải có Bearer Token.")

        parts = auth_header.strip().split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise ValueError("Định dạng Authorization Header không hợp lệ (cần 'Bearer <token>').")

        token = parts[1]
        payload = JWTService.decode(token, secret_key=secret_key)

        # Trích xuất và validate qua Pydantic DTO
        return UserSecurityContextDTO(
            user_id=str(payload.get("user_id", "anonymous")),
            username=str(payload.get("username", "anonymous")),
            tenant_code=str(payload.get("tenant_code", "68")),
            department_code=payload.get("department_code"),
            office_id=payload.get("office_id"),
            role_level=int(payload.get("role_level", 3))
        )

    @classmethod
    def generate_token_for_profile(
        cls,
        profile_key: str,
        secret_key: str = DEFAULT_JWT_SECRET,
        expires_in_seconds: int = 86400
    ) -> str:
        """Sinh mã JWT Token cho một trong các Profile mẫu chuẩn bị thử nghiệm."""
        if profile_key not in SAMPLE_ROLE_PROFILES:
            raise KeyError(f"Không tìm thấy profile '{profile_key}'. Danh sách hợp lệ: {list(SAMPLE_ROLE_PROFILES.keys())}")
        
        profile_data = SAMPLE_ROLE_PROFILES[profile_key]
        return JWTService.encode(profile_data, secret_key=secret_key, expires_in_seconds=expires_in_seconds)
