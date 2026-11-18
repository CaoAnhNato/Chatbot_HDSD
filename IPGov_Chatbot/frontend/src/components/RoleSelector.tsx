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
    id: "bf508c0c-79cc-4397-8b1c-82f716854568",
    user_id: "bf508c0c-79cc-4397-8b1c-82f716854568",
    username: "lanhdao",
    name: "Lãnh đạo",
    label: "Lãnh đạo",
    badge: "Level 4 • Lãnh đạo Toàn quyền",
    badge_label: "Level 4 • Lãnh đạo Toàn quyền",
    tenant_code: "79",
    tenant_name: "UBND Thành phố Hồ Chí Minh",
    department_code: "79-1-02",
    department_name: "UBND Phường Tam Bình",
    position: "Lãnh đạo",
    office_id: null,
    role_level: 4,
    is_unrestricted: true,
    assigned_mission_ids: [],
    assigned_mission_names: [],
    mission_count: 0,
  },
  {
    id: "e5779db2-0876-4674-937e-41fe0b12fa3d",
    user_id: "e5779db2-0876-4674-937e-41fe0b12fa3d",
    username: "hngoc",
    name: "Hồng Ngọc",
    label: "Hồng Ngọc",
    badge: "Level 3 • Quản trị Đa nhiệm vụ",
    badge_label: "Level 3 • Quản trị Đa nhiệm vụ",
    tenant_code: "79",
    tenant_name: "UBND Thành phố Hồ Chí Minh",
    department_code: "79-1-02",
    department_name: "UBND Phường Tam Bình",
    position: "Chuyên viên",
    office_id: null,
    role_level: 3,
    is_unrestricted: false,
    assigned_mission_ids: [
      "a7545ae7-5c98-4210-a7a5-a8f09605dd44",
      "94346f5c-4bce-4b55-80fb-7bf6ba40ba99",
      "4c23db4a-e9ff-4c2f-9dd2-8a0173aec2c4",
    ],
    assigned_mission_names: ["Trồng trọt", "Chăn nuôi", "Thuỷ sản"],
    mission_count: 3,
  },
  {
    id: "fe5401af-2059-4236-aa17-0b8fed1577e4",
    user_id: "fe5401af-2059-4236-aa17-0b8fed1577e4",
    username: "mnhat",
    name: "Minh Nhật",
    label: "Minh Nhật",
    badge: "Level 1 • Chuyên viên Đơn nhiệm",
    badge_label: "Level 1 • Chuyên viên Đơn nhiệm",
    tenant_code: "79",
    tenant_name: "UBND Thành phố Hồ Chí Minh",
    department_code: "79-1-02",
    department_name: "UBND Phường Tam Bình",
    position: "cv",
    office_id: null,
    role_level: 1,
    is_unrestricted: false,
    assigned_mission_ids: ["f0d27b88-e05a-47a5-bdaa-745ed551b348"],
    assigned_mission_names: ["Diêm nghiệp"],
    mission_count: 1,
  },
  {
    id: "9a8afbb0-92c4-444f-8584-7532311b1029",
    user_id: "9a8afbb0-92c4-444f-8584-7532311b1029",
    username: "kp12.tb",
    name: "Khu phố 12",
    label: "Khu phố 12",
    badge: "Level 1 • Chuyên viên Đơn nhiệm",
    badge_label: "Level 1 • Chuyên viên Đơn nhiệm",
    tenant_code: "79",
    tenant_name: "UBND Thành phố Hồ Chí Minh",
    department_code: "79-2-01",
    department_name: "Khu phố 12",
    position: "cv",
    office_id: null,
    role_level: 1,
    is_unrestricted: false,
    assigned_mission_ids: ["94346f5c-4bce-4b55-80fb-7bf6ba40ba99"],
    assigned_mission_names: ["Chăn nuôi"],
    mission_count: 1,
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
