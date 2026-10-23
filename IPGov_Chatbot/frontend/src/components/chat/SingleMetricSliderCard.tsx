'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { SingleMetricCardData, PinnedDrawerItem } from '@/types/chat';
import {
  Calendar,
  TrendingUp,
  TrendingDown,
  Minus,
  Pin,
  Building2,
  FolderKanban,
  Clock,
  SlidersHorizontal,
} from 'lucide-react';

interface SingleMetricSliderCardProps {
  card: SingleMetricCardData;
  onSelectChip?: (queryText: string) => void;
  onPinItem?: (item: PinnedDrawerItem) => void;
}

export const SingleMetricSliderCard: React.FC<SingleMetricSliderCardProps> = ({
  card,
  onSelectChip,
  onPinItem,
}) => {
  const criterionName = card.criterion_name || card.criteria_name || 'Chỉ tiêu số liệu';
  const baseActiveDate = (card.active_report_date || card.report_date || '').trim();
  const baseActiveValue = card.active_value || card.current_value || '-';
  const baseOffice = card.office_name || card.office || 'Cấp tỉnh';
  const baseMission = card.mission_name || card.mission || '';

  const snapshots = useMemo(
    () => (Array.isArray(card.timeline_snapshots) ? card.timeline_snapshots : []),
    [card.timeline_snapshots]
  );

  const initialIdx = useMemo(() => {
    if (snapshots.length === 0) return -1;
    if (baseActiveDate) {
      const found = snapshots.findIndex(
        (s) =>
          s.report_date === baseActiveDate ||
          s.date === baseActiveDate ||
          s.iso_date === baseActiveDate
      );
      if (found >= 0) return found;
    }
    return snapshots.length - 1;
  }, [snapshots, baseActiveDate]);

  const [selectedIdx, setSelectedIdx] = useState<number>(initialIdx);
  const [customDate, setCustomDate] = useState<string>('');
  const [localShiftNotice, setLocalShiftNotice] = useState<string | null>(null);

  useEffect(() => {
    setSelectedIdx(initialIdx);
    setLocalShiftNotice(null);
  }, [initialIdx, card.temporal_shift_notice]);

  const activeSnap =
    selectedIdx >= 0 && selectedIdx < snapshots.length ? snapshots[selectedIdx] : null;

  const displayValue = activeSnap ? activeSnap.value : baseActiveValue;
  const displayDate = activeSnap ? activeSnap.report_date || activeSnap.date || baseActiveDate : baseActiveDate || '-';
  const displayOffice = activeSnap?.office || baseOffice;
  const displayMission = activeSnap?.mission || baseMission;
  const effectiveShiftNotice = localShiftNotice ?? card.temporal_shift_notice ?? null;

  const handlePin = () => {
    if (!onPinItem) return;
    onPinItem({
      id: `pin-metric-${card.criterion_id || card.criteria_id || criterionName}-${displayDate}`,
      type: 'metric',
      title: `${criterionName} (${displayDate})`,
      subtitle: `${card.parent_name ? `${card.parent_name} • ` : ''}${displayOffice}`,
      temporal_scope: card.temporal_scope,
      payload: {
        ...card,
        criterion_name: criterionName,
        active_value: displayValue,
        active_report_date: displayDate,
        office_name: displayOffice,
        mission_name: displayMission,
        selected_snapshot: activeSnap,
        temporal_shift_notice: effectiveShiftNotice || undefined,
      },
      pinnedAt: new Date().toISOString(),
    });
  };

  const applyCustomDate = (isoDateVal: string) => {
    const trimmed = (isoDateVal || '').trim();
    if (!trimmed) return;

    // Normalize DD/MM/YYYY if entered manually
    let normalizedIso = trimmed;
    let formattedVn = trimmed;
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(trimmed)) {
      const [dd, mm, yyyy] = trimmed.split('/');
      normalizedIso = `${yyyy}-${mm}-${dd}`;
      formattedVn = trimmed;
    } else if (/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) {
      const [yyyy, mm, dd] = trimmed.split('-');
      formattedVn = `${dd}/${mm}/${yyyy}`;
    }

    if (snapshots.length > 0) {
      const exactIdx = snapshots.findIndex(
        (s) => s.iso_date === normalizedIso || s.report_date === formattedVn || s.date === formattedVn
      );
      if (exactIdx >= 0) {
        setSelectedIdx(exactIdx);
        setLocalShiftNotice(null);
        return;
      }

      const targetMs = Date.parse(`${normalizedIso}T00:00:00Z`);
      if (!Number.isNaN(targetMs)) {
        const parsedSnaps = snapshots
          .map((s, idx) => {
            let iso = s.iso_date || '';
            if (!iso && (s.report_date || s.date)) {
              const dStr = (s.report_date || s.date || '').trim();
              if (/^\d{2}\/\d{2}\/\d{4}$/.test(dStr)) {
                const [d, m, y] = dStr.split('/');
                iso = `${y}-${m}-${d}`;
              }
            }
            const ms = Date.parse(`${iso}T00:00:00Z`);
            return { snap: s, idx, ms, vn: s.report_date || s.date || iso };
          })
          .filter((item) => !Number.isNaN(item.ms))
          .sort((a, b) => a.ms - b.ms);

        if (parsedSnaps.length > 0) {
          let lower: (typeof parsedSnaps)[0] | null = null;
          let upper: (typeof parsedSnaps)[0] | null = null;
          for (const item of parsedSnaps) {
            if (item.ms <= targetMs) lower = item;
            if (item.ms >= targetMs && !upper) upper = item;
          }
          const chosen =
            lower && upper
              ? Math.abs(targetMs - lower.ms) <= Math.abs(upper.ms - targetMs)
                ? lower
                : upper
              : lower || upper || parsedSnaps[parsedSnaps.length - 1];

          const deltaDays = Math.round(Math.abs(targetMs - chosen.ms) / 86400000);
          const boundParts: string[] = [];
          if (lower) boundParts.push(`kỳ trước: ${lower.vn}`);
          if (upper && (!lower || upper.vn !== lower.vn)) {
            boundParts.push(`kỳ kế tiếp: ${upper.vn}`);
          }
          const boundNote = boundParts.length > 0 ? ` — ${boundParts.join(', ')}` : '';
          setSelectedIdx(chosen.idx);
          setLocalShiftNotice(
            `Ngày tra cứu ${formattedVn} không trùng đợt chốt sổ (lệch ${deltaDays} ngày); hệ thống đối chiếu mốc gần nhất ngày ${chosen.vn}${boundNote}`
          );
          return;
        }
      }
    }

    // Fallback: trigger SC-2.2 custom date query on chat stream
    const parentClause = card.parent_name ? ` thuộc nhóm ${card.parent_name}` : '';
    onSelectChip?.(
      `Cho tôi biết số liệu chỉ tiêu ${criterionName}${parentClause} tính đến ngày ${formattedVn} năm 2026?`
    );
  };

  return (
    <div
      data-testid="metric-slider-time"
      className="not-prose my-3 rounded-2xl border border-indigo-200/90 bg-gradient-to-br from-white via-indigo-50/20 to-slate-50 p-4 shadow-sm transition-all hover:shadow-md"
    >
      {/* Header: Criterion Name + Parent Badge + Pin Button */}
      <div className="flex flex-wrap items-start justify-between gap-2 pb-3 border-b border-slate-200/80">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-700 text-[11px] font-bold">
              <SlidersHorizontal className="w-3 h-3" />
              Ticket slider-time • 0ms
            </span>
            {(card.parent_name || card.hierarchy_label || card.hierarchy_badge) && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[11px] font-medium border border-slate-200">
                {card.parent_name ? (
                  <>
                    Nhóm gốc: <strong>{card.parent_name}</strong>
                  </>
                ) : (
                  card.hierarchy_label || card.hierarchy_badge
                )}
              </span>
            )}
            {(card.temporal_scope?.label || card.temporal_scope?.period_label) && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 text-[11px] font-semibold border border-blue-200">
                <Clock className="w-3 h-3" />
                {card.temporal_scope?.label || card.temporal_scope?.period_label}
              </span>
            )}
          </div>
          <h4 className="text-sm font-bold text-slate-900 leading-snug">{criterionName}</h4>
        </div>

        {onPinItem && (
          <button
            type="button"
            data-testid="pin-item-button"
            onClick={handlePin}
            title="Ghim chỉ tiêu này sang khay tham chiếu bên phải (Split-Screen)"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border border-slate-200 hover:border-indigo-300 text-xs font-semibold transition shadow-2xs cursor-pointer"
          >
            <Pin className="w-3.5 h-3.5 text-indigo-600" />
            <span>📌 Ghim</span>
          </button>
        )}
      </div>

      {/* Main Value + Delta Comparison + Metadata */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 my-3 items-center">
        <div className="rounded-xl bg-white border border-slate-200/90 p-3 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Số liệu phê duyệt ({displayDate})
          </div>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              data-testid="slider-active-value"
              className="text-2xl font-extrabold font-mono text-indigo-700"
            >
              {displayValue}
            </span>
            {activeSnap?.delta_prev !== null && activeSnap?.delta_prev !== undefined && (
              <span
                data-testid="slider-delta-badge"
                className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[11px] font-bold ${
                  activeSnap.delta_prev > 0
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : activeSnap.delta_prev < 0
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : 'bg-slate-100 text-slate-600 border border-slate-200'
                }`}
              >
                {activeSnap.delta_prev > 0 ? (
                  <TrendingUp className="w-3 h-3" />
                ) : activeSnap.delta_prev < 0 ? (
                  <TrendingDown className="w-3 h-3" />
                ) : (
                  <Minus className="w-3 h-3" />
                )}
                {activeSnap.delta_prev > 0 ? `+${activeSnap.delta_prev}` : activeSnap.delta_prev}
                {activeSnap.delta_pct !== null && activeSnap.delta_pct !== undefined
                  ? ` (${activeSnap.delta_pct > 0 ? '+' : ''}${activeSnap.delta_pct}%)`
                  : ''}
              </span>
            )}
          </div>
        </div>

        <div className="rounded-xl bg-white border border-slate-200/90 p-3 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1">
            <Building2 className="w-3 h-3 text-slate-400" />
            Đơn vị thực hiện
          </div>
          <div className="mt-1 text-xs font-bold text-slate-800 truncate" title={displayOffice}>
            {displayOffice}
          </div>
        </div>

        <div className="rounded-xl bg-white border border-slate-200/90 p-3 shadow-2xs">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1">
            <FolderKanban className="w-3 h-3 text-slate-400" />
            Nhiệm vụ / Biểu mẫu
          </div>
          <div
            className="mt-1 text-xs font-bold text-slate-800 truncate"
            title={displayMission || 'Báo cáo định kỳ 2026'}
          >
            {displayMission || 'Báo cáo định kỳ 2026'}
          </div>
        </div>
      </div>

      {/* Temporal Shift Notice Banner (PA 1.1 Dual-Bound Snapshot) */}
      {effectiveShiftNotice && (
        <div
          data-testid="slider-temporal-shift-notice"
          className="my-2.5 flex items-start gap-2 rounded-xl border border-amber-300/90 bg-amber-50/90 px-3 py-2 text-xs text-amber-900 shadow-2xs"
        >
          <Clock className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">Lưu ý mốc thời gian: </span>
            <span>{effectiveShiftNotice}</span>
          </div>
        </div>
      )}

      {/* Interactive Timeline Slider & Period Pills */}
      {snapshots.length > 0 ? (
        <div className="mt-3 pt-3 border-t border-slate-200/80 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[11px] font-semibold text-slate-600 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-indigo-600" />
              Trượt chọn kỳ báo cáo ({snapshots.length} mốc phê duyệt • 0ms Client-side):
            </span>

            {/* Custom Date Picker for SC-2.2 */}
            <div className="flex items-center gap-1.5">
              <label className="text-[11px] text-slate-500 font-medium">Ngày tùy chỉnh:</label>
              <input
                type="date"
                data-testid="slider-custom-date-input"
                value={customDate}
                onChange={(e) => {
                  setCustomDate(e.target.value);
                  applyCustomDate(e.target.value);
                }}
                className="px-2 py-0.5 text-[11px] rounded-md border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              />
              <button
                type="button"
                data-testid="slider-custom-date-apply"
                onClick={() => applyCustomDate(customDate)}
                className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 transition cursor-pointer"
              >
                Áp dụng
              </button>
            </div>
          </div>

          {snapshots.length > 1 && (
            <input
              type="range"
              data-testid="metric-timeline-range"
              min={0}
              max={snapshots.length - 1}
              step={1}
              value={selectedIdx >= 0 ? selectedIdx : snapshots.length - 1}
              onChange={(e) => {
                setSelectedIdx(Number(e.target.value));
                setLocalShiftNotice(null);
              }}
              className="w-full h-1.5 bg-indigo-100 rounded-lg appearance-none cursor-pointer accent-indigo-600"
            />
          )}

          <div className="flex flex-wrap items-center gap-1.5">
            {snapshots.map((snap, idx) => {
              const isSelected = idx === selectedIdx;
              const snapDate = snap.report_date || snap.date;
              return (
                <button
                  key={`${snapDate}-${idx}`}
                  type="button"
                  data-testid={`slider-period-pill-${idx}`}
                  onClick={() => {
                    setSelectedIdx(idx);
                    setLocalShiftNotice(null);
                  }}
                  className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer border ${
                    isSelected
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-xs'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-indigo-50 hover:border-indigo-300'
                  }`}
                >
                  <span>{snap.period_label || snapDate}</span>
                  <span
                    className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                      isSelected ? 'bg-indigo-500 text-white' : 'bg-slate-100 text-slate-700'
                    }`}
                  >
                    {snap.value}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="mt-2 pt-2 border-t border-slate-200/70 flex items-center justify-between text-[11px] text-amber-700 bg-amber-50/70 px-3 py-1.5 rounded-lg border border-amber-200/60">
          <span>Chỉ tiêu hiện chưa có lịch sử biến động qua các kỳ báo cáo đã phê duyệt.</span>
        </div>
      )}
    </div>
  );
};
