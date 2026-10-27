"""
Warehouse Ground-Truth Checker for Render Scheduled Automation Suite.
Queries the IPGov Warehouse (PostgreSQL vna_wom_dev / DuckDB Semantic Catalog)
to provide authoritative ground-truth values across all reporting periods
(31/03/2026, 30/06/2026, 30/09/2026, Quý 1, Quý 2, Quý 3, Năm 2026).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from IPGov_Chatbot.modules.mod04_catalog.duckdb_semantic_catalog import DuckDBSemanticCatalog


class WarehouseGroundTruthChecker:
    """Provides direct Warehouse Ground Truth lookup and answer verification."""

    def __init__(self) -> None:
        self.catalog = DuckDBSemanticCatalog()

    def get_hierarchy_children_ground_truth(self, parent_code: str) -> Dict[str, Any]:
        """Returns canonical ordered children and their period values from Warehouse."""
        conn = self.catalog.conn
        parent_row = conn.execute(
            """
            SELECT id, code, name, level
            FROM catalog_criteria_hierarchy
            WHERE LOWER(code) = LOWER(?)
            LIMIT 1
            """,
            [parent_code],
        ).fetchone()
        if not parent_row:
            return {"found": False, "parent_code": parent_code}

        parent_id, p_code, p_name, p_level = parent_row
        children = conn.execute(
            """
            SELECT id, code, name, level, latest_value, office_name, mission_name
            FROM catalog_criteria_hierarchy
            WHERE parent_id = ?
            ORDER BY level ASC, created_date ASC, id ASC
            """,
            [parent_id],
        ).fetchall()

        child_nodes = [
            {
                "id": str(r[0]),
                "code": str(r[1]),
                "name": str(r[2]),
                "level": int(r[3] or 3),
                "latest_value": str(r[4]) if r[4] is not None else "-",
                "office_name": str(r[5] or "Chi cục"),
                "mission_name": str(r[6] or "-"),
            }
            for r in children
        ]
        child_names = [n["name"] for n in child_nodes]
        child_codes = [n["code"] for n in child_nodes]
        latest_vector = [n["latest_value"] for n in child_nodes]

        batch_periods = self.catalog.get_batch_period_values(nodes=child_nodes)

        return {
            "found": True,
            "parent_id": parent_id,
            "parent_code": p_code,
            "parent_name": p_name,
            "level": p_level,
            "child_count": len(children),
            "canonical_order_names": child_names,
            "canonical_order_codes": child_codes,
            "latest_vector": latest_vector,
            "batch_periods": batch_periods,
        }

    def get_single_criterion_timeline(
        self, criterion_name: str, parent_hint: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns timeline snapshots for a single criterion from Warehouse."""
        timeline = self.catalog.get_criterion_timeline_snapshots(
            criteria_name=criterion_name,
            parent_name=parent_hint,
        )
        return timeline or []

    def dump_reference_snapshot(self) -> Dict[str, Any]:
        """Dumps complete ground-truth snapshot for the 10 UI quests and 20 Backend quests."""
        return {
            "htx_efficiency_4_levels": self.get_hierarchy_children_ground_truth("hieu_qua_hoat_dong"),
            "htx_fields_8_items": self.get_hierarchy_children_ground_truth("so_luong_htx_phan_theo_linh_vuc"),
            "lhhtx_fields_8_items": self.get_hierarchy_children_ground_truth("tong_so_lhhtx_phan_theo_linh_vuc"),
            "salt_area_2_types": self.get_hierarchy_children_ground_truth("tong_dien_tich_san_xuat_muoi"),
            "salt_households_timeline": self.get_single_criterion_timeline("Tổng hộ sản xuất muối"),
            "lhhtx_chan_nuoi_timeline": self.get_single_criterion_timeline(
                "Chăn nuôi", parent_hint="Tổng số LHHTX phân theo lĩnh vực"
            ),
        }


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    checker = WarehouseGroundTruthChecker()
    snapshot = checker.dump_reference_snapshot()
    out_path = PROJECT_ROOT / "IPGov_Chatbot" / "data" / "reports" / "render_automation" / "warehouse_ground_truth_snapshot.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved Warehouse Ground Truth Snapshot successfully.")
