/**
 * Module: IPGov_Chatbot/frontend/components/RoleSelector.tsx
 * Chức năng: Component chọn nhanh vai trò (Role Selector) phục vụ kiểm thử và phân quyền HBAC
 * Tương thích: React 18+, Next.js 14+ (App Router hoặc Pages Router)
 * Tuân thủ tiêu chuẩn: TypeScript strict mode, Tailwind CSS
 */

import React, { useState, useEffect } from "react";

export interface UserRoleProfile {
  id: string;
  label: string;
  badge: string;
  tenant_code: string;
  tenant_name: string;
  department_code: string | null;
  office_id: string | null;
  role_level: number;
  user_id: string;
  username: string;
}

export const PRESET_ROLES: UserRoleProfile[] = [
  {
    id: "lamdong_leader",
    label: "Lãnh đạo UBND Tỉnh Lâm Đồng",
    badge: "Level 0 • Tỉnh",
    tenant_code: "68",
    tenant_name: "Tỉnh Lâm Đồng",
    department_code: null,
    office_id: null,
    role_level: 0,
    user_id: "u_ld_001",
    username: "lanhdao_ubnd_lamdong"
  },
  {
    id: "hcm_leader",
    label: "Lãnh đạo UBND TP. Hồ Chí Minh",
    badge: "Level 0 • Tỉnh",
    tenant_code: "79",
    tenant_name: "TP. Hồ Chí Minh",
    department_code: null,
    office_id: null,
    role_level: 0,
    user_id: "u_hcm_001",
    username: "lanhdao_ubnd_hcm"
  },
  {
    id: "lamdong_dept_noivu",
    label: "Lãnh đạo Sở Nội Vụ Lâm Đồng",
    badge: "Level 1 • Sở",
    tenant_code: "68",
    tenant_name: "Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    office_id: null,
    role_level: 1,
    user_id: "u_snv_001",
    username: "lanhdao_sonoi_vu"
  },
  {
    id: "lamdong_phong_kinhte",
    label: "Trưởng Phòng Kinh Tế (H. Đức Trọng)",
    badge: "Level 2 • Phòng",
    tenant_code: "68",
    tenant_name: "Tỉnh Lâm Đồng",
    department_code: "68-1-02",
    office_id: "Phòng Kinh tế",
    role_level: 2,
    user_id: "u_pkt_001",
    username: "truongphong_kinhte_lamdong"
  },
  {
    id: "lamdong_phong_xaydung",
    label: "Trưởng Phòng Xây Dựng (TP. Đà Lạt)",
    badge: "Level 2 • Phòng",
    tenant_code: "68",
    tenant_name: "Tỉnh Lâm Đồng",
    department_code: "68-1-03",
    office_id: "Phòng Xây dựng",
    role_level: 2,
    user_id: "u_pxd_001",
    username: "truongphong_xaydung_lamdong"
  },
  {
    id: "public_citizen",
    label: "Người Dân / Doanh Nghiệp (Public)",
    badge: "Level 3 • Công Dân",
    tenant_code: "68",
    tenant_name: "Tỉnh Lâm Đồng",
    department_code: null,
    office_id: null,
    role_level: 3,
    user_id: "u_pub_999",
    username: "congdan_tra_cuu"
  }
];

export interface RoleSelectorProps {
  selectedRole?: UserRoleProfile;
  onRoleSelect: (role: UserRoleProfile, mockToken: string) => void;
  className?: string;
}

/**
 * Sinh mock JWT token client-side cho mục đích test bench UI
 */
export function generateMockJWT(profile: UserRoleProfile): string {
  const header = { alg: "HS256", typ: "JWT" };
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    sub: profile.user_id,
    username: profile.username,
    tenant_code: profile.tenant_code,
    department_code: profile.department_code,
    office_id: profile.office_id,
    role_level: profile.role_level,
    iat: now,
    exp: now + 3600
  };
  const b64 = (obj: object) =>
    typeof window !== "undefined"
      ? btoa(unescape(encodeURIComponent(JSON.stringify(obj))))
          .replace(/=/g, "")
          .replace(/\+/g, "-")
          .replace(/\//g, "_")
      : Buffer.from(JSON.stringify(obj)).toString("base64url");

  return `${b64(header)}.${b64(payload)}.mock_client_signature`;
}

export const RoleSelector: React.FC<RoleSelectorProps> = ({
  selectedRole = PRESET_ROLES[0],
  onRoleSelect,
  className = ""
}) => {
  const [current, setCurrent] = useState<UserRoleProfile>(selectedRole);
  const [showToken, setShowToken] = useState<boolean>(false);

  useEffect(() => {
    setCurrent(selectedRole);
  }, [selectedRole]);

  const handleSelect = (profile: UserRoleProfile) => {
    setCurrent(profile);
    const token = generateMockJWT(profile);
    onRoleSelect(profile, token);
  };

  const getBadgeColor = (level: number) => {
    switch (level) {
      case 0:
        return "bg-emerald-950 text-emerald-300 border-emerald-800";
      case 1:
        return "bg-indigo-950 text-indigo-300 border-indigo-800";
      case 2:
        return "bg-amber-950 text-amber-300 border-amber-800";
      default:
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className={`bg-slate-900 rounded-2xl border border-slate-800 p-5 shadow-xl text-slate-100 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            Phân Quyền Thử Nghiệm (HBAC Roles)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">Chọn nhanh vai trò người dùng để kiểm thử Module 1 &amp; Module 2</p>
        </div>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700">
          HBAC Level: {current.role_level}
        </span>
      </div>

      <!-- Danh sách vai trò -->
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
        {PRESET_ROLES.map((role) => {
          const isSelected = role.id === current.id;
          return (
            <button
              key={role.id}
              onClick={() => handleSelect(role)}
              className={`text-left p-3 rounded-xl border transition-all duration-150 flex flex-col justify-between gap-2 ${
                isSelected
                  ? "bg-cyan-950/40 border-cyan-500/80 ring-1 ring-cyan-500/40 shadow-md shadow-cyan-950/40"
                  : "bg-slate-950/60 border-slate-800 hover:border-slate-700 hover:bg-slate-800/40"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold text-slate-200 leading-snug">{role.label}</span>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border whitespace-nowrap ${getBadgeColor(role.role_level)}`}>
                  {role.badge}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 font-mono flex items-center gap-2">
                <span>tenant: {role.tenant_code}</span>
                <span>•</span>
                <span>dept: {role.department_code || "ALL"}</span>
                {role.office_id && (
                  <>
                    <span>•</span>
                    <span className="truncate">{role.office_id}</span>
                  </>
                )}
              </div>
            </button>
          );
        })}
      </div>

      <!-- Chi tiết ngữ cảnh bảo mật đang chọn -->
      <div className="mt-4 p-3.5 rounded-xl bg-slate-950/80 border border-slate-800/80 text-xs">
        <div className="flex items-center justify-between text-slate-400 mb-2">
          <span>Ngữ cảnh bảo mật hiện thời:</span>
          <span className="font-mono text-cyan-400 font-semibold">{current.username}</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 font-mono text-[11px]">
          <div className="bg-slate-900 p-2 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px]">TENANT CODE</span>
            <span className="text-emerald-400 font-bold">{current.tenant_code}</span>
          </div>
          <div className="bg-slate-900 p-2 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px]">HBAC LEVEL</span>
            <span className="text-amber-400 font-bold">{current.role_level}</span>
          </div>
          <div className="bg-slate-900 p-2 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px]">DEPARTMENT</span>
            <span className="text-slate-300 truncate block">{current.department_code || "NULL"}</span>
          </div>
          <div className="bg-slate-900 p-2 rounded border border-slate-800">
            <span className="text-slate-500 block text-[9px]">OFFICE ID</span>
            <span className="text-slate-300 truncate block">{current.office_id || "NULL"}</span>
          </div>
        </div>

        <div className="mt-2.5 pt-2 border-t border-slate-800/80 flex items-center justify-between">
          <button
            onClick={() => setShowToken(!showToken)}
            className="text-[11px] text-slate-400 hover:text-slate-200 underline font-mono"
          >
            {showToken ? "Ẩn JWT Bearer Token" : "Hiện JWT Bearer Token mẫu"}
          </button>
          <span className="text-[10px] text-slate-500">RFC 7519 • HS256</span>
        </div>

        {showToken && (
          <div className="mt-2 p-2 rounded bg-slate-900 border border-slate-800 font-mono text-[10px] text-slate-400 break-all select-all">
            Bearer {generateMockJWT(current)}
          </div>
        )}
      </div>
    </div>
  );
};

export default RoleSelector;
