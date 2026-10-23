'use client';

import React, { useState } from 'react';
import { PinnedDrawerItem } from '@/types/chat';
import {
  Pin,
  X,
  Trash2,
  FolderTree,
  Table as TableIcon,
  BarChart3,
  Clock,
  Search,
  Building2,
} from 'lucide-react';

function normalizeVn(str: string): string {
  return (str || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim();
}

interface PinnedReferenceDrawerProps {
  items: PinnedDrawerItem[];
  activeTabId: string | null;
  onSelectTab: (id: string) => void;
  onUnpin: (id: string) => void;
  onClearAll: () => void;
  onSelectChip?: (queryText: string) => void;
  toastMessage?: string | null;
}

export const PinnedReferenceDrawer: React.FC<PinnedReferenceDrawerProps> = ({
  items,
  activeTabId,
  onSelectTab,
  onUnpin,
  onClearAll,
  onSelectChip,
  toastMessage,
}) => {
  const [drawerSearch, setDrawerSearch] = useState<string>('');

  if (!items || items.length === 0) return null;

  const activeItem = items.find((i) => i.id === activeTabId) || items[0];
  const temporalSuffix = activeItem?.temporal_scope?.query_suffix || 'năm 2026';
  const temporalLabel =
    activeItem?.temporal_scope?.label || activeItem?.temporal_scope?.period_label || null;
  const normSearch = normalizeVn(drawerSearch);

  const renderTreePreview = (item: PinnedDrawerItem) => {
    const rawRoot = item.payload?.rootNode || item.payload;
    const rootName = rawRoot?.name || item.title;
    const rawL2List: any[] = Array.isArray(rawRoot?.children) ? rawRoot.children : [];
    const l2List = !normSearch
      ? rawL2List
      : rawL2List.filter((l2: any) => {
          if (normalizeVn(l2?.name || '').includes(normSearch)) return true;
          const l3s: any[] = Array.isArray(l2?.children) ? l2.children : [];
          return l3s.some((l3) => normalizeVn(l3?.name || '').includes(normSearch));
        });

    return (
      <div className="space-y-2.5">
        <div className="rounded-xl bg-indigo-50/70 border border-indigo-200 p-3">
          <div className="text-[11px] font-bold text-indigo-700 uppercase">Nhóm Cấp 1 đã ghim</div>
          <div className="text-sm font-bold text-slate-900 mt-0.5">{rootName}</div>
          {rawRoot?.office_name && (
            <div className="text-[11px] text-slate-600 mt-1 flex items-center gap-1">
              <Building2 className="w-3 h-3 text-slate-400" />
              <span>{rawRoot.office_name}</span>
            </div>
          )}
        </div>

        <div className="space-y-2">
          {l2List.map((l2: any, idx: number) => {
            const rawL3List: any[] = Array.isArray(l2?.children) ? l2.children : [];
            const l3List =
              !normSearch || normalizeVn(l2?.name || '').includes(normSearch)
                ? rawL3List
                : rawL3List.filter((l3) => normalizeVn(l3?.name || '').includes(normSearch));
            const hasVal =
              l2?.value !== null &&
              l2?.value !== undefined &&
              String(l2.value).trim() !== '' &&
              String(l2.value).trim() !== '-';

            return (
              <div
                key={l2?.id || idx}
                className="rounded-xl border border-slate-200 bg-white p-3 space-y-2 shadow-2xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="text-xs font-bold text-slate-800 leading-snug">
                    Cấp 2: {l2?.name}
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold shrink-0 ${
                      hasVal
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-slate-100 text-slate-600 border border-slate-200'
                    }`}
                  >
                    {hasVal ? String(l2.value) : l3List.length > 0 ? `${l3List.length} con` : '-'}
                  </span>
                </div>

                {l3List.length === 0 ? (
                  <div className="flex justify-end">
                    <button
                      type="button"
                      data-testid={`pinned-drilldown-${idx}`}
                      onClick={() =>
                        onSelectChip?.(
                          `Cho tôi biết số liệu chỉ tiêu ${l2?.name} thuộc nhóm ${rootName} ${temporalSuffix}?`
                        )
                      }
                      className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white border border-indigo-200 text-[11px] font-semibold transition cursor-pointer"
                    >
                      <Search className="w-3 h-3" />
                      <span>Tra cứu ({temporalSuffix})</span>
                    </button>
                  </div>
                ) : (
                  <div className="pl-2.5 border-l-2 border-indigo-100 space-y-1.5">
                    {l3List.map((l3: any, l3Idx: number) => {
                      const l3Val =
                        l3?.value !== null &&
                        l3?.value !== undefined &&
                        String(l3.value).trim() !== '' &&
                        String(l3.value).trim() !== '-'
                          ? String(l3.value)
                          : '-';
                      return (
                        <div
                          key={l3?.id || l3Idx}
                          className="flex items-center justify-between gap-2 text-[11px] bg-slate-50/80 px-2.5 py-1.5 rounded-lg border border-slate-100"
                        >
                          <span className="font-medium text-slate-700 truncate" title={l3?.name}>
                            • {l3?.name}
                          </span>
                          <div className="flex items-center gap-1.5 shrink-0">
                            <span
                              className={`px-1.5 py-0.5 rounded font-mono font-bold ${
                                l3Val !== '-'
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                  : 'bg-amber-50 text-amber-700 border border-amber-200'
                              }`}
                            >
                              {l3Val}
                            </span>
                            <button
                              type="button"
                              data-testid={`pinned-drilldown-l3-${idx}-${l3Idx}`}
                              onClick={() =>
                                onSelectChip?.(
                                  `Cho tôi biết số liệu chỉ tiêu ${l3?.name} thuộc nhóm ${rootName} ${temporalSuffix}?`
                                )
                              }
                              title={`Tra cứu ${l3?.name} (${temporalSuffix})`}
                              className="px-1.5 py-0.5 rounded bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white border border-indigo-200 font-semibold transition cursor-pointer"
                            >
                              🔍
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const renderTablePreview = (item: PinnedDrawerItem) => {
    const cols: any[] = Array.isArray(item.payload?.columns) ? item.payload.columns : [];
    const rawRows: any[] = Array.isArray(item.payload?.rows) ? item.payload.rows : [];
    const rows = !normSearch
      ? rawRows
      : rawRows.filter((r) =>
          Object.values(r || {}).some((v) => normalizeVn(String(v ?? '')).includes(normSearch))
        );

    const handleRowDrilldown = (r: any) => {
      if (!onSelectChip) return;
      if (typeof r?.action_query === 'string' && r.action_query.trim()) {
        onSelectChip(r.action_query.trim());
        return;
      }
      const rawName =
        r?.item ||
        r?.ten_chi_tieu_cap_1 ||
        r?.ten_chi_tieu ||
        r?.mission_name ||
        r?.name ||
        '';
      const cleanName = String(rawName).replace(/\*\*|`/g, '').trim();
      if (!cleanName) return;
      const rawCat = String(r?.category || '')
        .replace(/\*\(Cấp.*?\)\*/g, '')
        .replace(/\*\*|`/g, '')
        .trim();
      const isStructuralMetaLabel =
        !rawCat ||
        rawCat === '-' ||
        rawCat.includes('Nhóm chỉ tiêu') ||
        rawCat.includes('Chỉ tiêu đơn') ||
        rawCat.includes('Chỉ tiêu gốc');
      const parentCtx = !isStructuralMetaLabel ? ` thuộc nhóm ${rawCat}` : '';
      onSelectChip(
        `Cho tôi biết số liệu chỉ tiêu ${cleanName}${parentCtx} ${temporalSuffix}?`
      );
    };

    return (
      <div className="space-y-2">
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left border-collapse text-[11px]">
            <thead className="bg-slate-100 border-b border-slate-200 text-slate-700">
              <tr>
                {cols.slice(0, 4).map((c: any) => (
                  <th key={c.key} className="py-1.5 px-2 font-bold whitespace-nowrap">
                    {c.label}
                  </th>
                ))}
                {onSelectChip && (
                  <th className="py-1.5 px-2 font-bold text-center whitespace-nowrap">Tra cứu</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((r: any, rIdx: number) => (
                <tr key={rIdx} className="odd:bg-white even:bg-slate-50/50 hover:bg-indigo-50/40">
                  {cols.slice(0, 4).map((c: any) => (
                    <td key={c.key} className="py-1.5 px-2 text-slate-700">
                      {String(r[c.key] ?? '-').replace(/^\*\*|\*\*$/g, '')}
                    </td>
                  ))}
                  {onSelectChip && (
                    <td className="py-1.5 px-2 text-center">
                      <button
                        type="button"
                        data-testid={`pinned-table-drilldown-${rIdx}`}
                        onClick={() => handleRowDrilldown(r)}
                        title={`Tra cứu sâu (${temporalSuffix})`}
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-50 hover:bg-indigo-600 text-indigo-700 hover:text-white border border-indigo-200 text-[10px] font-semibold transition cursor-pointer"
                      >
                        🔍
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="text-[11px] text-slate-400 italic text-center">
          Đang hiển thị {rows.length}/{rawRows.length} dòng trong khay ghim ({temporalSuffix})
        </div>
      </div>
    );
  };

  const renderMetricPreview = (item: PinnedDrawerItem) => {
    const card = item.payload || {};
    const snaps: any[] = Array.isArray(card.timeline_snapshots) ? card.timeline_snapshots : [];

    return (
      <div className="space-y-3">
        <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-3.5">
          <div className="text-[11px] font-semibold text-indigo-700">
            {card.parent_name || 'Chỉ tiêu đơn lẻ'}
          </div>
          <div className="text-sm font-bold text-slate-900 mt-0.5">{card.criterion_name}</div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-extrabold font-mono text-indigo-700">
              {card.active_value || '-'}
            </span>
            <span className="text-xs text-slate-500">
              (Kỳ: {card.active_report_date || '-'})
            </span>
          </div>
          {card.office_name && (
            <div className="text-[11px] text-slate-600 mt-1.5">
              Đơn vị: <strong>{card.office_name}</strong>
            </div>
          )}
        </div>

        {snaps.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-3 space-y-1.5">
            <div className="text-[11px] font-bold text-slate-700">Lịch sử qua các kỳ phê duyệt:</div>
            {snaps.map((s: any, idx: number) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs py-1 px-2 rounded bg-slate-50 border border-slate-100"
              >
                <span className="font-medium text-slate-700">{s.period_label || s.date}</span>
                <span className="font-mono font-bold text-indigo-700">{s.value}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <aside
      data-testid="pinned-reference-drawer"
      className="fixed inset-y-0 right-0 w-full max-w-[100vw] sm:static sm:w-96 shrink-0 border-l border-slate-200 bg-slate-50/95 flex flex-col h-full overflow-hidden shadow-lg z-30"
    >
      {/* Header */}
      <div className="px-4 py-3 bg-white border-b border-slate-200 flex items-center justify-between gap-2 shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-100 text-indigo-700 flex items-center justify-center">
            <Pin className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold text-slate-800">
              Khay Tham Chiếu Đã Ghim ({items.length}/3)
            </h3>
            <p className="text-[10px] text-slate-500">Split-Screen • Không trôi khi chat tiếp</p>
          </div>
        </div>

        <button
          type="button"
          data-testid="pinned-clear-all"
          onClick={onClearAll}
          title="Bỏ ghim tất cả"
          className="px-2 py-1 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-200 text-[11px] font-semibold inline-flex items-center gap-1 transition cursor-pointer"
        >
          <Trash2 className="w-3 h-3" />
          <span>Xóa hết</span>
        </button>
      </div>

      {/* Overflow / Info Toast */}
      {toastMessage && (
        <div
          data-testid="pinned-drawer-toast"
          className="mx-3 mt-2 px-3 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-medium"
        >
          {toastMessage}
        </div>
      )}

      {/* Tabs (Max 3) */}
      <div className="px-3 pt-2.5 pb-2 bg-slate-100/80 border-b border-slate-200 flex items-center gap-1.5 overflow-x-auto shrink-0">
        {items.map((tab, idx) => {
          const isActive = tab.id === activeItem.id;
          return (
            <div
              key={tab.id}
              data-testid={`pinned-tab-${idx}`}
              onClick={() => onSelectTab(tab.id)}
              className={`group flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer border transition max-w-[160px] ${
                isActive
                  ? 'bg-indigo-600 text-white border-indigo-600 shadow-2xs'
                  : 'bg-white text-slate-700 border-slate-200 hover:bg-indigo-50'
              }`}
            >
              {tab.type === 'tree' ? (
                <FolderTree className="w-3.5 h-3.5 shrink-0" />
              ) : tab.type === 'metric' ? (
                <BarChart3 className="w-3.5 h-3.5 shrink-0" />
              ) : (
                <TableIcon className="w-3.5 h-3.5 shrink-0" />
              )}
              <span className="truncate" title={tab.title}>
                {tab.title}
              </span>
              <button
                type="button"
                data-testid={`unpin-tab-${idx}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onUnpin(tab.id);
                }}
                title="Bỏ ghim thẻ này"
                className={`p-0.5 rounded hover:bg-black/10 transition ${
                  isActive ? 'text-white' : 'text-slate-400 hover:text-rose-600'
                }`}
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          );
        })}
      </div>

      {/* Active Tab Metadata Bar + Quick Search */}
      <div className="px-3.5 py-2 bg-white border-b border-slate-200/80 space-y-2 shrink-0">
        <div className="flex items-center justify-between gap-2 text-[11px]">
          <span className="font-semibold text-slate-700 truncate" title={activeItem.subtitle}>
            {activeItem.subtitle || activeItem.title}
          </span>
          {temporalLabel && (
            <span
              data-testid="pinned-active-temporal-badge"
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 font-semibold shrink-0"
            >
              <Clock className="w-3 h-3" />
              {temporalLabel}
            </span>
          )}
        </div>
        {(activeItem.type === 'table' || activeItem.type === 'tree') && (
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              data-testid="pinned-drawer-search-input"
              value={drawerSearch}
              onChange={(e) => setDrawerSearch(e.target.value)}
              placeholder="Tìm nhanh trong khay ghim..."
              className="w-full pl-7 pr-6 py-1 text-[11px] rounded-lg border border-slate-200 bg-slate-50 focus:bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {drawerSearch && (
              <button
                type="button"
                onClick={() => setDrawerSearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Body Content */}
      <div className="p-3.5 overflow-y-auto flex-1 space-y-3">
        {activeItem.type === 'tree'
          ? renderTreePreview(activeItem)
          : activeItem.type === 'metric'
          ? renderMetricPreview(activeItem)
          : renderTablePreview(activeItem)}
      </div>
    </aside>
  );
};
