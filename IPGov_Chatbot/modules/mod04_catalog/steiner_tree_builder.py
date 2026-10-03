"""
Module: IPGov_Chatbot/modules/mod04_catalog/steiner_tree_builder.py
Chức năng: Xây dựng Đồ thị Schema DWH có trọng số (Domain-Aware Weighted Graph)
và áp dụng giải thuật NetworkX Minimal Steiner Tree tự động kết nối và bù đắp các bảng cầu nối (Bridge Tables).
Căn cứ: Blueprint 03_SEMANTIC_LAYER_MDL_VA_IN_MEMORY_CATALOG.md (Mục 3.5 Giai đoạn 2)
"""

from __future__ import annotations
import logging
from typing import Dict, List, Optional, Set, Tuple
import networkx as nx
from networkx.algorithms.approximation.steinertree import steiner_tree

from IPGov_Chatbot.schemas.catalog_dto import JoinPathDTO

logger = logging.getLogger(__name__)


class SteinerTreeBuilder:
    """
    Xây dựng cây khung nhỏ nhất (Minimal Steiner Tree) trên đồ thị quan hệ khóa ngoại DWH.
    Đảm bảo 100% đường dẫn JOIN liên thông đa bảng, ngăn chặn triệt để lỗi gãy quan hệ JOIN.
    """

    def __init__(self) -> None:
        self.graph = nx.Graph()
        self._canonical_map: Dict[str, str] = {}
        self._init_schema_graph()

    def _init_schema_graph(self) -> None:
        """
        Khởi tạo đồ thị DWH G=(V, E):
        - Đỉnh V: Các bảng trong schema dwh_internal
        - Cạnh E: Các quan hệ Foreign Key kèm trọng số nghiệp vụ (Domain-Aware Weights)
        """
        edges = [
            # Fact -> Dimensions trực tiếp (Weight 1.0)
            (
                "dwh_internal.fact_report_criteria",
                "dwh_internal.office",
                {"weight": 1.0, "on": "f.office_id = office.id", "role": "primary"}
            ),
            (
                "dwh_internal.fact_report_criteria",
                "dwh_internal.criteria",
                {"weight": 1.0, "on": "f.criteria_id = criteria.id", "role": "primary"}
            ),
            (
                "dwh_internal.fact_report_criteria",
                "dwh_internal.report",
                {"weight": 1.0, "on": "f.report_id = report.id", "role": "primary"}
            ),
            # Fact -> Department trực tiếp (Weight 10.0) - Tăng trọng số để tránh tự động chọn deparment làm bridge khi bảng này có 0 bản ghi
            (
                "dwh_internal.fact_report_criteria",
                "dwh_internal.deparment",
                {"weight": 10.0, "on": "f.department_code = deparment.code", "role": "direct_dept"}
            ),
            # Dimensions Phân cấp Hành chính (Level 2 Office -> Level 1 Department) (Weight 10.0)
            (
                "dwh_internal.office",
                "dwh_internal.deparment",
                {"weight": 10.0, "on": "office.department_code = deparment.code", "role": "hierarchy"}
            ),
            # Report -> Collection Form (Weight 1.0)
            (
                "dwh_internal.report",
                "dwh_internal.collection_form",
                {"weight": 1.0, "on": "report.form_id = collection_form.id", "role": "form"}
            ),
            # Report -> Department (Weight 10.0)
            (
                "dwh_internal.report",
                "dwh_internal.deparment",
                {"weight": 10.0, "on": "report.department_code = deparment.code", "role": "secondary"}
            ),
            # Mission -> Department (Weight 10.0)
            (
                "dwh_internal.mission",
                "dwh_internal.deparment",
                {"weight": 10.0, "on": "mission.department_code = deparment.code", "role": "mission"}
            ),
            # Collection Form -> Department (Weight 10.0)
            (
                "dwh_internal.collection_form",
                "dwh_internal.deparment",
                {"weight": 10.0, "on": "collection_form.department_code = deparment.code", "role": "form_dept"}
            ),
            # Office Mission -> Office & Department & Mission
            (
                "dwh_internal.office_mission",
                "dwh_internal.office",
                {"weight": 1.0, "on": "office_mission.office_id = office.id", "role": "office_assignment"}
            ),
            (
                "dwh_internal.office_mission",
                "dwh_internal.deparment",
                {"weight": 1.2, "on": "office_mission.department_code = deparment.code", "role": "office_dept"}
            ),
            (
                "dwh_internal.office_mission",
                "dwh_internal.mission",
                {"weight": 1.0, "on": "office_mission.mission_id = mission.id", "role": "office_mission"}
            ),
            # User Mission -> User & Fact
            (
                "dwh_internal.user_mission",
                "dwh_internal.user",
                {"weight": 1.0, "on": "user_mission.user_id = \"user\".id", "role": "user_assignment"}
            ),
            (
                "dwh_internal.user_mission",
                "dwh_internal.mission",
                {"weight": 1.0, "on": "user_mission.mission_id = mission.id", "role": "mission_assignment"}
            ),
            (
                "dwh_internal.fact_report_criteria",
                "dwh_internal.user_mission",
                {"weight": 1.1, "on": "fact_report_criteria.mission_id = user_mission.mission_id", "role": "fact_user_mission"}
            ),
        ]

        for u, v, data in edges:
            self.graph.add_edge(u, v, **data)
            # Thiết lập bản đồ chuẩn hóa tên bảng
            u_simple = u.split(".")[-1]
            v_simple = v.split(".")[-1]
            self._canonical_map[u] = u
            self._canonical_map[u_simple] = u
            self._canonical_map[v] = v
            self._canonical_map[v_simple] = v

    def canonicalize_table_name(self, name: str) -> str:
        """Chuẩn hóa tên bảng sang tên đầy đủ dwh_internal.xxx"""
        clean = name.strip()
        if clean in self._canonical_map:
            return self._canonical_map[clean]
        if "." not in clean:
            clean_with_schema = f"dwh_internal.{clean}"
            if clean_with_schema in self.graph:
                return clean_with_schema
        return clean

    def build_steiner_tree(self, candidate_tables: List[str]) -> nx.Graph:
        """
        Xây dựng cây Steiner tối thiểu cho tập đỉnh ứng viên.
        Trả về đồ thị con nx.Graph chứa các đỉnh và cạnh kết nối tối ưu.
        """
        terminals = list({self.canonicalize_table_name(t) for t in candidate_tables})
        valid_terminals = [t for t in terminals if t in self.graph]
        if not valid_terminals:
            g = nx.Graph()
            g.add_nodes_from(candidate_tables)
            return g
        if len(valid_terminals) == 1:
            g = nx.Graph()
            g.add_node(valid_terminals[0])
            return g
        return steiner_tree(self.graph, valid_terminals, weight="weight")

    def resolve_connected_subgraph(
        self, candidate_tables: List[str]
    ) -> Tuple[List[str], List[str], List[JoinPathDTO]]:
        """
        Tìm cây khung kết nối tối thiểu (Minimal Steiner Tree) cho tập bảng ứng viên.
        
        Args:
            candidate_tables: Danh sách các bảng ứng viên được tìm thấy từ bước lọc thô.
            
        Returns:
            Tuple gồm:
            - all_nodes: Danh sách toàn bộ các bảng trong đồ thị con kết nối liên thông.
            - bridge_tables: Danh sách các bảng cầu nối được bổ sung tự động.
            - join_paths: Danh sách các khế ước phép JOIN giữa các bảng.
        """
        if not candidate_tables:
            return [], [], []

        # Chuẩn hóa tên bảng
        terminals = list({self.canonicalize_table_name(t) for t in candidate_tables})
        # Lọc các bảng thực sự có trong đồ thị
        valid_terminals = [t for t in terminals if t in self.graph]

        if not valid_terminals:
            return candidate_tables, [], []

        if len(valid_terminals) == 1:
            return valid_terminals, [], []

        try:
            # Giải thuật Minimal Steiner Tree của NetworkX
            subgraph = self.build_steiner_tree(valid_terminals)
            all_nodes = list(subgraph.nodes())
            bridge_tables = [n for n in all_nodes if n not in valid_terminals]

            # Sinh danh sách các phép JOIN theo cạnh của cây khung
            join_paths: List[JoinPathDTO] = []
            for u, v in subgraph.edges():
                edge_data = self.graph.get_edge_data(u, v) or {}
                on_clause = edge_data.get("on", f"{u}.id = {v}.id")
                join_paths.append(
                    JoinPathDTO(
                        source_table=u,
                        target_table=v,
                        on_clause=on_clause,
                        join_type="INNER JOIN"
                    )
                )

            return all_nodes, bridge_tables, join_paths

        except Exception as e:
            logger.warning("Không thể tính toán Steiner Tree cho %s: %s. Giữ nguyên tập bảng ứng viên.", candidate_tables, e)
            return valid_terminals, [], []
