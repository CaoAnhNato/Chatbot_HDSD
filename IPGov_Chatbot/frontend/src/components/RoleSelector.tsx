/**
 * Module: frontend/src/components/RoleSelector.tsx
 * Chức năng: Component chọn nhanh vai trò (Role Selector) phục vụ kiểm thử và phân quyền HBAC
 * Tương thích: React 18+, Next.js 14+ (App Router hoặc Pages Router)
 * Tuân thủ tiêu chuẩn: TypeScript strict mode, Tailwind CSS
 */

import React, { useState, useEffect } from "react";

export interface UserRoleProfile {
  id: string;
  user_id: string;
  username: string;
  name: string;
  label: string;
  badge: string;
  badge_label: string;
  tenant_code: string;
  tenant_name: string;
  department_code: string | null;
  department_name?: string;
  position?: string;
  office_id?: string | null;
  role_level: number;
  is_unrestricted: boolean;
  assigned_mission_ids: string[];
  assigned_mission_names: string[];
  mission_count: number;
}

export const PRESET_ROLES: UserRoleProfile[] = [
  {
    id: "035b1733-943b-4993-b50c-96ec2ece5e74",
    user_id: "035b1733-943b-4993-b50c-96ec2ece5e74",
    username: "boss",
    name: "Lãnh đạo",
    label: "Lãnh đạo",
    badge: "Level 4 • Lãnh đạo Toàn quyền",
    badge_label: "Level 4 • Lãnh đạo Toàn quyền",
    tenant_code: "68",
    tenant_name: "UBND Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    department_name: "UBND Tỉnh Lâm Đồng",
    position: "qtv",
    office_id: null,
    role_level: 4,
    is_unrestricted: true,
    assigned_mission_ids: [],
    assigned_mission_names: [],
    mission_count: 0,
  },
  {
    id: "2ebf478e-f245-43c3-816b-27a0a42099ed",
    user_id: "2ebf478e-f245-43c3-816b-27a0a42099ed",
    username: "bacgianghia.ld",
    name: "Phường Bắc Gia Nghĩa",
    label: "Phường Bắc Gia Nghĩa",
    badge: "Level 3 • Quản trị Đa nhiệm vụ",
    badge_label: "Level 3 • Quản trị Đa nhiệm vụ",
    tenant_code: "68",
    tenant_name: "Phường Bắc Gia Nghĩa",
    department_code: "68-2-01",
    department_name: "Phường Bắc Gia Nghĩa",
    position: "QTV",
    office_id: null,
    role_level: 3,
    is_unrestricted: false,
    assigned_mission_ids: [
      "4feb96a8-6145-4a31-a58b-3851cccd015a",
      "78b71984-b96a-40bd-8f9d-045a7239df8e",
      "7ee83ad6-d613-4ab3-8b74-b179b4428182",
    ],
    assigned_mission_names: ["Phát triển nông thôn", "Diêm nghiệp", "Trồng trọt"],
    mission_count: 3,
  },
  {
    id: "af12924c-189c-4a39-857d-f3839990a4fd",
    user_id: "af12924c-189c-4a39-857d-f3839990a4fd",
    username: "admin-lamdong",
    name: "Admin Tỉnh Lâm Đồng",
    label: "Admin Tỉnh Lâm Đồng",
    badge: "Level 3 • Quản trị Đa nhiệm vụ",
    badge_label: "Level 3 • Quản trị Đa nhiệm vụ",
    tenant_code: "68",
    tenant_name: "UBND Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    department_name: "UBND Tỉnh Lâm Đồng",
    position: "QTV",
    office_id: null,
    role_level: 3,
    is_unrestricted: false,
    assigned_mission_ids: [
      "52c54734-5bbe-4b38-a021-260818831c60",
      "855c7f67-6029-47a2-aa83-dc60c9589698",
      "7bb5b602-eeb7-49d5-9be6-0ae8d3ff38ac",
    ],
    assigned_mission_names: ["Nhiệm vụ 4 ASXH", "Nhiệm vụ 3 ASXH", "Nhiệm vụ 1 ASXH"],
    mission_count: 3,
  },
  {
    id: "c981c2b8-03ae-4a22-982c-6d84654c27c9",
    user_id: "c981c2b8-03ae-4a22-982c-6d84654c27c9",
    username: "hngoc",
    name: "Hồng Ngọc",
    label: "Hồng Ngọc",
    badge: "Level 2 • Chuyên trách Đa ngành",
    badge_label: "Level 2 • Chuyên trách Đa ngành",
    tenant_code: "68",
    tenant_name: "UBND Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    department_name: "UBND Tỉnh Lâm Đồng",
    position: "qtv",
    office_id: null,
    role_level: 2,
    is_unrestricted: false,
    assigned_mission_ids: [
      "4feb96a8-6145-4a31-a58b-3851cccd015a",
      "0d34a260-073d-4e42-9224-97fcc8eb8b24",
    ],
    assigned_mission_names: ["Phát triển nông thôn", "Lao động, tiền lương"],
    mission_count: 2,
  },
  {
    id: "dda87792-26bf-4ce6-8cb7-0fdb02b07ea9",
    user_id: "dda87792-26bf-4ce6-8cb7-0fdb02b07ea9",
    username: "minhanh",
    name: "Minh Anh",
    label: "Minh Anh",
    badge: "Level 1 • Chuyên viên Đơn nhiệm",
    badge_label: "Level 1 • Chuyên viên Đơn nhiệm",
    tenant_code: "68",
    tenant_name: "UBND Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    department_name: "UBND Tỉnh Lâm Đồng",
    position: "cv",
    office_id: null,
    role_level: 1,
    is_unrestricted: false,
    assigned_mission_ids: ["604c00c3-e7e2-488e-8305-6800e672e99b"],
    assigned_mission_names: ["Công nghiệp"],
    mission_count: 1,
  },
  {
    id: "48bb6688-6c97-4239-8892-56950b416237",
    user_id: "48bb6688-6c97-4239-8892-56950b416237",
    username: "donggianghia.ld",
    name: "UBND phường Đông Gia Nghĩa",
    label: "UBND phường Đông Gia Nghĩa",
    badge: "Level 1 • Chuyên viên Đơn nhiệm",
    badge_label: "Level 1 • Chuyên viên Đơn nhiệm",
    tenant_code: "68",
    tenant_name: "Phường Đông Gia Nghĩa",
    department_code: "68-2-02",
    department_name: "Phường Đông Gia Nghĩa",
    position: "QTV",
    office_id: null,
    role_level: 1,
    is_unrestricted: false,
    assigned_mission_ids: ["7ee83ad6-d613-4ab3-8b74-b179b4428182"],
    assigned_mission_names: ["Trồng trọt"],
    mission_count: 1,
  },
  {
    id: "96239497-6417-4f24-b730-b6f4a2b2a07e",
    user_id: "96239497-6417-4f24-b730-b6f4a2b2a07e",
    username: "ubnd-lamdong",
    name: "UBND Tỉnh Lâm Đồng",
    label: "UBND Tỉnh Lâm Đồng",
    badge: "Level 1 • Chuyên viên Đơn nhiệm",
    badge_label: "Level 1 • Chuyên viên Đơn nhiệm",
    tenant_code: "68",
    tenant_name: "UBND Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    department_name: "UBND Tỉnh Lâm Đồng",
    position: "qtv",
    office_id: null,
    role_level: 1,
    is_unrestricted: false,
    assigned_mission_ids: ["96c1d5b1-f14b-4177-a31a-0a9220baab01"],
    assigned_mission_names: ["Test"],
    mission_count: 1,
  },
  {
    id: "cc99047a-692d-49f8-aacc-f3f8031a445b",
    user_id: "cc99047a-692d-49f8-aacc-f3f8031a445b",
    username: "tzyalnh",
    name: "Nguyễn Thị Thúy Lành",
    label: "Nguyễn Thị Thúy Lành",
    badge: "Level 0 • Cán bộ Cơ sở (Giới hạn)",
    badge_label: "Level 0 • Cán bộ Cơ sở (Giới hạn)",
    tenant_code: "68",
    tenant_name: "UBND Tỉnh Lâm Đồng",
    department_code: "68-1-01",
    department_name: "UBND Tỉnh Lâm Đồng",
    position: "BA",
    office_id: null,
    role_level: 0,
    is_unrestricted: false,
    assigned_mission_ids: [],
    assigned_mission_names: [],
    mission_count: 0,
  },
];

export function getLevelBadgeStyle(level: number): {
  chipClass: string;
  badgeColor: string;
} {
  switch (level) {
    case 4:
      return {
        chipClass: "bg-purple-100 text-purple-800 border-purple-300 font-bold",
        badgeColor: "bg-purple-950 text-purple-300 border-purple-800",
      };
    case 3:
      return {
        chipClass: "bg-blue-100 text-blue-800 border-blue-300 font-semibold",
        badgeColor: "bg-blue-950 text-blue-300 border-blue-800",
      };
    case 2:
      return {
        chipClass: "bg-emerald-100 text-emerald-800 border-emerald-300 font-semibold",
        badgeColor: "bg-emerald-950 text-emerald-300 border-emerald-800",
      };
    case 1:
      return {
        chipClass: "bg-sky-100 text-sky-800 border-sky-300 font-medium",
        badgeColor: "bg-sky-950 text-sky-300 border-sky-800",
      };
    case 0:
    default:
      return {
        chipClass: "bg-slate-100 text-slate-700 border-slate-300 font-medium",
        badgeColor: "bg-slate-900 text-slate-300 border-slate-700",
      };
  }
}

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
    user_id: profile.user_id,
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

  return `${b64(header)}.${b64(payload)}.mock_sig_pass`;
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
    return getLevelBadgeStyle(level).badgeColor;
  };

  return (
    <div className={`bg-slate-900 rounded-2xl border border-slate-800 p-5 shadow-xl text-slate-100 ${className}`}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            Phân Quyền Thử Nghiệm (HBAC Roles)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">Chọn nhanh vai trò người dùng để kiểm thử phân quyền DWH</p>
        </div>
        <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700">
          HBAC Level: {current.role_level}
        </span>
      </div>

      {/* Danh sách vai trò */}
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

      {/* Chi tiết ngữ cảnh bảo mật đang chọn */}
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
