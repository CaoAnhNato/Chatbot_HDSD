"""
Module: IPGov_Chatbot/modules/mod01_gateway/user_service.py
Chức năng: Quản lý danh mục tài khoản công vụ, phân cấp quyền hạn theo nhiệm vụ (5 bậc thẩm quyền)
và cung cấp giao diện truy xuất động từ PostgreSQL dwh_internal."user" kèm cơ chế fallback an toàn.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from IPGov_Chatbot.modules.mod07_dwh_exec.connection_pool import DWHConnectionPool
from IPGov_Chatbot.schemas.user_context import UserSecurityContextDTO

logger = logging.getLogger("ipgov.mod01.user_service")

# ---------------------------------------------------------------------------
# FALLBACK PRE-SEEDED DATA (8 TÀI KHOẢN CÔNG VỤ CHUẨN TRONG KHO DWH vna_wom_dev)
# ---------------------------------------------------------------------------
PRE_SEEDED_USERS: List[Dict[str, Any]] = [
    {
        "id": "035b1733-943b-4993-b50c-96ec2ece5e74",
        "username": "boss",
        "name": "Lãnh đạo",
        "department_code": "68-1-01",
        "department_name": "UBND Tỉnh Lâm Đồng",
        "position": "qtv",
        "role_level": 4,
        "badge_label": "Level 4 • Lãnh đạo Toàn quyền",
        "is_unrestricted": True,
        "assigned_mission_ids": [],
        "assigned_mission_names": [],
        "mission_count": 0,
    },
    {
        "id": "2ebf478e-f245-43c3-816b-27a0a42099ed",
        "username": "bacgianghia.ld",
        "name": "Phường Bắc Gia Nghĩa",
        "department_code": "68-2-01",
        "department_name": "Phường Bắc Gia Nghĩa",
        "position": "QTV",
        "role_level": 3,
        "badge_label": "Level 3 • Quản trị Đa nhiệm vụ",
        "is_unrestricted": False,
        "assigned_mission_ids": [
            "4feb96a8-6145-4a31-a58b-3851cccd015a",
            "78b71984-b96a-40bd-8f9d-045a7239df8e",
            "7ee83ad6-d613-4ab3-8b74-b179b4428182",
        ],
        "assigned_mission_names": [
            "Phát triển nông thôn",
            "Diêm nghiệp",
            "Trồng trọt",
        ],
        "mission_count": 3,
    },
    {
        "id": "af12924c-189c-4a39-857d-f3839990a4fd",
        "username": "admin-lamdong",
        "name": "Admin Tỉnh Lâm Đồng",
        "department_code": "68-1-01",
        "department_name": "UBND Tỉnh Lâm Đồng",
        "position": "QTV",
        "role_level": 3,
        "badge_label": "Level 3 • Quản trị Đa nhiệm vụ",
        "is_unrestricted": False,
        "assigned_mission_ids": [
            "52c54734-5bbe-4b38-a021-260818831c60",
            "855c7f67-6029-47a2-aa83-dc60c9589698",
            "7bb5b602-eeb7-49d5-9be6-0ae8d3ff38ac",
        ],
        "assigned_mission_names": [
            "Nhiệm vụ 4 ASXH",
            "Nhiệm vụ 3 ASXH",
            "Nhiệm vụ 1 ASXH",
        ],
        "mission_count": 3,
    },
    {
        "id": "c981c2b8-03ae-4a22-982c-6d84654c27c9",
        "username": "hngoc",
        "name": "Hồng Ngọc",
        "department_code": "68-1-01",
        "department_name": "UBND Tỉnh Lâm Đồng",
        "position": "qtv",
        "role_level": 2,
        "badge_label": "Level 2 • Chuyên trách Đa ngành",
        "is_unrestricted": False,
        "assigned_mission_ids": [
            "4feb96a8-6145-4a31-a58b-3851cccd015a",
            "0d34a260-073d-4e42-9224-97fcc8eb8b24",
        ],
        "assigned_mission_names": [
            "Phát triển nông thôn",
            "Lao động, tiền lương",
        ],
        "mission_count": 2,
    },
    {
        "id": "dda87792-26bf-4ce6-8cb7-0fdb02b07ea9",
        "username": "minhanh",
        "name": "Minh Anh",
        "department_code": "68-1-01",
        "department_name": "UBND Tỉnh Lâm Đồng",
        "position": "cv",
        "role_level": 1,
        "badge_label": "Level 1 • Chuyên viên Đơn nhiệm",
        "is_unrestricted": False,
        "assigned_mission_ids": [
            "604c00c3-e7e2-488e-8305-6800e672e99b",
        ],
        "assigned_mission_names": [
            "Công nghiệp",
        ],
        "mission_count": 1,
    },
    {
        "id": "48bb6688-6c97-4239-8892-56950b416237",
        "username": "donggianghia.ld",
        "name": "UBND phường Đông Gia Nghĩa",
        "department_code": "68-2-02",
        "department_name": "Phường Đông Gia Nghĩa",
        "position": "QTV",
        "role_level": 1,
        "badge_label": "Level 1 • Chuyên viên Đơn nhiệm",
        "is_unrestricted": False,
        "assigned_mission_ids": [
            "7ee83ad6-d613-4ab3-8b74-b179b4428182",
        ],
        "assigned_mission_names": [
            "Trồng trọt",
        ],
        "mission_count": 1,
    },
    {
        "id": "96239497-6417-4f24-b730-b6f4a2b2a07e",
        "username": "ubnd-lamdong",
        "name": "UBND Tỉnh Lâm Đồng",
        "department_code": "68-1-01",
        "department_name": "UBND Tỉnh Lâm Đồng",
        "position": "qtv",
        "role_level": 1,
        "badge_label": "Level 1 • Chuyên viên Đơn nhiệm",
        "is_unrestricted": False,
        "assigned_mission_ids": [
            "96c1d5b1-f14b-4177-a31a-0a9220baab01",
        ],
        "assigned_mission_names": [
            "Test",
        ],
        "mission_count": 1,
    },
    {
        "id": "cc99047a-692d-49f8-aacc-f3f8031a445b",
        "username": "tzyalnh",
        "name": "Nguyễn Thị Thúy Lành",
        "department_code": "68-1-01",
        "department_name": "UBND Tỉnh Lâm Đồng",
        "position": "BA",
        "role_level": 0,
        "badge_label": "Level 0 • Cán bộ Cơ sở (Giới hạn)",
        "is_unrestricted": False,
        "assigned_mission_ids": [],
        "assigned_mission_names": [],
        "mission_count": 0,
    },
]


def classify_account(
    name: str,
    username: str,
    assigned_mission_ids: List[str],
    assigned_mission_names: List[str],
) -> Dict[str, Any]:
    """
    Phân cấp tài khoản thành 5 bậc thẩm quyền dựa trên số lượng/loại nhiệm vụ:
    - Level 4: name = 'Lãnh đạo' (Unrestricted Executive Tier)
    - Level 3: >= 3 missions
    - Level 2: 2 missions
    - Level 1: 1 mission
    - Level 0: 0 missions
    """
    clean_name = (name or "").strip()
    clean_username = (username or "").strip().lower()

    if clean_name == "Lãnh đạo" or clean_username == "boss":
        return {
            "role_level": 4,
            "badge_label": "Level 4 • Lãnh đạo Toàn quyền",
            "is_unrestricted": True,
        }

    mission_count = len(assigned_mission_ids)
    if mission_count >= 3:
        return {
            "role_level": 3,
            "badge_label": "Level 3 • Quản trị Đa nhiệm vụ",
            "is_unrestricted": False,
        }
    elif mission_count == 2:
        return {
            "role_level": 2,
            "badge_label": "Level 2 • Chuyên trách Đa ngành",
            "is_unrestricted": False,
        }
    elif mission_count == 1:
        return {
            "role_level": 1,
            "badge_label": "Level 1 • Chuyên viên Đơn nhiệm",
            "is_unrestricted": False,
        }
    else:
        return {
            "role_level": 0,
            "badge_label": "Level 0 • Cán bộ Cơ sở (Giới hạn)",
            "is_unrestricted": False,
        }


class UserService:
    """
    Service quản lý và đồng bộ danh sách tài khoản từ PostgreSQL dwh_internal."user"
    và dwh_internal.user_mission với fallback offline.
    """

    _instance: Optional[UserService] = None

    def __init__(self) -> None:
        self._cached_users: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def get_instance(cls) -> UserService:
        if cls._instance is None:
            cls._instance = UserService()
        return cls._instance

    async def get_users(self, force_refresh: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """
        Truy vấn danh sách tài khoản động từ CSDL PostgreSQL.
        Nếu gặp sự cố mạng hoặc offline, trả về 8 tài khoản pre-seeded chuẩn.
        """
        if self._cached_users is not None and not force_refresh:
            return {"users": self._cached_users}

        users_list: List[Dict[str, Any]] = []
        try:
            pool = await asyncio.wait_for(DWHConnectionPool.get_instance().get_pool(), timeout=2.0)
            async with pool.acquire() as conn:
                # Bảng "user" là từ khóa dành riêng nên cần đặt trong dấu nháy kép theo TRAPS
                sql = """
                    SELECT 
                        u.id::text AS id,
                        u.username,
                        u.name,
                        u.department_code,
                        u.department_name,
                        u.position,
                        COALESCE(ARRAY_AGG(um.mission_id::text) FILTER (WHERE um.mission_id IS NOT NULL), '{}') AS mission_ids,
                        COALESCE(ARRAY_AGG(um.mission_name::text) FILTER (WHERE um.mission_name IS NOT NULL), '{}') AS mission_names
                    FROM dwh_internal."user" u
                    LEFT JOIN dwh_internal.user_mission um ON u.id = um.user_id AND um.deleted_date IS NULL
                    WHERE u.deleted_at IS NULL
                    GROUP BY u.id, u.username, u.name, u.department_code, u.department_name, u.position
                    ORDER BY u.id;
                """
                records = await asyncio.wait_for(conn.fetch(sql), timeout=3.0)
                for r in records:
                    m_ids = list(r["mission_ids"] or [])
                    m_names = list(r["mission_names"] or [])
                    # Loại bỏ trùng lặp nếu có
                    unique_pairs = []
                    seen_ids = set()
                    for mid, mname in zip(m_ids, m_names):
                        if mid not in seen_ids:
                            seen_ids.add(mid)
                            unique_pairs.append((mid, mname))
                    filtered_ids = [p[0] for p in unique_pairs]
                    filtered_names = [p[1] for p in unique_pairs]

                    classification = classify_account(
                        name=r["name"] or "",
                        username=r["username"] or "",
                        assigned_mission_ids=filtered_ids,
                        assigned_mission_names=filtered_names,
                    )

                    users_list.append({
                        "id": str(r["id"]),
                        "username": r["username"] or "",
                        "name": r["name"] or "",
                        "department_code": r["department_code"] or "",
                        "department_name": r["department_name"] or "",
                        "position": r["position"] or "",
                        "role_level": classification["role_level"],
                        "badge_label": classification["badge_label"],
                        "is_unrestricted": classification["is_unrestricted"],
                        "assigned_mission_ids": filtered_ids,
                        "assigned_mission_names": filtered_names,
                        "mission_count": len(filtered_ids),
                    })

                if users_list:
                    self._cached_users = users_list
                    return {"users": users_list}
        except Exception as exc:
            logger.warning("Không thể truy vấn dwh_internal.\"user\" động: %s. Kích hoạt fallback offline.", exc)

        # Fallback offline
        self._cached_users = list(PRE_SEEDED_USERS)
        return {"users": list(PRE_SEEDED_USERS)}

    def find_user_sync(self, identifier: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Tìm kiếm tài khoản đồng bộ theo id, username hoặc name (ưu tiên cached_users hoặc PRE_SEEDED_USERS).
        """
        if not identifier:
            return None
        clean_id = str(identifier).strip().lower()
        candidates_source = self._cached_users or PRE_SEEDED_USERS
        for u in candidates_source:
            u_id = str(u.get("id") or "").lower()
            u_user = str(u.get("username") or "").lower()
            u_name = str(u.get("name") or "").lower()
            if u_id == clean_id or u_user == clean_id or u_name == clean_id:
                return dict(u)
            # Hỗ trợ alias không dấu hoặc viết tắt
            if clean_id in ("boss", "lanhdao", "lanh_dao", "lanh dao", "lãnh đạo", "leader") and (u_user == "boss" or "lãnh đạo" in u_name):
                return dict(u)
            if clean_id in ("thuylanh", "thuy_lanh", "tzyalnh", "thúy lành") and (u_user == "tzyalnh" or "thúy lành" in u_name):
                return dict(u)
            if clean_id in ("hongngoc", "hong_ngoc", "hngoc", "hồng ngọc") and (u_user == "hngoc" or "hồng ngọc" in u_name):
                return dict(u)
            if clean_id in ("minhanh", "minh_anh", "minh anh") and (u_user == "minhanh" or "minh anh" in u_name):
                return dict(u)
            if clean_id in ("bacgianghia", "bac_gia_nghia", "bacgianghia.ld") and ("bắc gia nghĩa" in u_name or u_user == "bacgianghia.ld"):
                return dict(u)
            if clean_id in ("donggianghia", "dong_gia_nghia", "donggianghia.ld") and ("đông gia nghĩa" in u_name or u_user == "donggianghia.ld"):
                return dict(u)
        return None

    def build_user_context(
        self,
        user_identifier: Optional[str] = None,
        role_level: Optional[int] = None,
        schema: str = "dwh_internal",
        tenant_code: Optional[str] = None,
        department_code: Optional[str] = None,
    ) -> UserSecurityContextDTO:
        """
        Xây dựng đối tượng UserSecurityContextDTO hoàn chỉnh kèm phân cấp và danh mục nhiệm vụ.
        Cưỡng chế Zero Trust & Least Privilege:
        1. Người dùng có trong CSDL: role_level và is_unrestricted lấy TUYỆT ĐỐI từ profile CSDL.
        2. Người dùng không xác định (attacker/guest): Bắt buộc hạ cấp về Level 0 (Guest), is_unrestricted=False.
        """
        clean_schema = "dwh_public" if str(schema or "").strip().lower() == "dwh_public" else "dwh_internal"
        profile = self.find_user_sync(user_identifier)
        if profile:
            db_role_level = int(profile.get("role_level", 0))
            if role_level is not None and role_level != db_role_level:
                logger.warning(
                    "CẢNH BÁO AN NINH (RBAC): Yêu cầu gán role_level=%s cho người dùng '%s' "
                    "bị từ chối. Cưỡng chế theo CSDL: level=%s.",
                    role_level, profile.get("username"), db_role_level,
                )

            active_level = db_role_level
            is_unrestricted = bool(profile.get("is_unrestricted", False))

            dept_code = department_code or profile.get("department_code")
            t_code = tenant_code or (profile.get("department_code") or "68")[:2] or "68"

            return UserSecurityContextDTO(
                user_id=profile["id"],
                username=profile["username"],
                name=profile["name"],
                user_name=profile["name"],
                tenant_code=t_code,
                department_code=dept_code,
                role_level=active_level,
                schema=clean_schema,
                assigned_mission_ids=profile.get("assigned_mission_ids", []),
                assigned_mission_names=profile.get("assigned_mission_names", []),
                is_unrestricted=is_unrestricted,
            )

        # Mặc định công dân / khách vãng lai nếu không tìm thấy trong CSDL
        if user_identifier or role_level is not None:
            logger.info(
                "Định danh '%s' (role_level đề xuất: %s) không tồn tại trong CSDL. "
                "Cưỡng chế hạ về Khách vãng lai (Level 0, is_unrestricted=False).",
                user_identifier, role_level,
            )

        return UserSecurityContextDTO(
            user_id="default_user",
            username=user_identifier or "guest",
            name="Khách vãng lai",
            user_name="Khách vãng lai",
            tenant_code=tenant_code or "68",
            department_code=department_code,
            role_level=0,
            schema=clean_schema,
            assigned_mission_ids=[],
            assigned_mission_names=[],
            is_unrestricted=False,
        )


user_service = UserService.get_instance()
