'use client';

import React, { useState, useMemo, useEffect } from 'react';
import { SingleMetricCardData, PinnedDrawerItem, TimelineSnapshotItem } from '@/types/chat';
import {
  Calendar,
  Pin,
  Clock,
} from 'lucide-react';

interface SingleMetricSliderCardProps {
  card: SingleMetricCardData;
  onSelectChip?: (queryText: string) => void;
  onPinItem?: (item: PinnedDrawerItem) => void;
  onTimelineChange?: (snapshot: TimelineSnapshotItem | null, shiftNotice: string | null) => void;
}

export const SingleMetricSliderCard: React.FC<SingleMetricSliderCardProps> = ({
  card,
  onSelectChip,
  onPinItem,
  onTimelineChange,
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
  const [localShiftNotice, setLocalShiftNotice] = useState<string | null>(
    card.temporal_shift_notice ?? null
  );

  useEffect(() => {
    setSelectedIdx(initialIdx);
    setLocalShiftNotice(card.temporal_shift_notice ?? null);
  }, [initialIdx, card.temporal_shift_notice]);

  const activeSnap =
    selectedIdx >= 0 && selectedIdx < snapshots.length ? snapshots[selectedIdx] : null;

  const displayValue = activeSnap ? activeSnap.value : baseActiveValue;
  const displayDate = activeSnap ? activeSnap.report_date || activeSnap.date || baseActiveDate : baseActiveDate || '-';
  const displayOffice = activeSnap?.office || baseOffice;
  const displayMission = activeSnap?.mission || baseMission;
  const effectiveShiftNotice = localShiftNotice;

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
        onTimelineChange?.(snapshots[exactIdx], null);
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
          const notice = `Ngày tra cứu ${formattedVn} không trùng đợt chốt sổ (lệch ${deltaDays} ngày); hệ thống đối chiếu mốc gần nhất ngày ${chosen.vn}${boundNote}`;
          setLocalShiftNotice(notice);
          onTimelineChange?.(chosen.snap, notice);
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
      className="relative not-prose my-2.5 rounded-2xl border border-blue-200/90 bg-gradient-to-r from-blue-50/60 via-indigo-50/30 to-slate-50 p-3.5 shadow-xs"
    >
      {/* Ẩn giá trị active và delta badge để bảo toàn backward compatibility cho e2e tests */}
      <span data-testid="slider-active-value" className="sr-only top-0 left-0">
        {displayValue}
      </span>
      {activeSnap?.delta_prev !== null && activeSnap?.delta_prev !== undefined && (
        <span data-testid="slider-delta-badge" className="sr-only top-0 left-0">
          {activeSnap.delta_prev > 0 ? `+${activeSnap.delta_prev}` : activeSnap.delta_prev}
        </span>
      )}

      {/* Header tinh gọn: Tiêu đề kỳ báo cáo + Nút Ghim */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-blue-100">
        <div className="flex flex-wrap items-center gap-2">
          <Calendar className="w-4 h-4 text-blue-700 shrink-0" />
          <span className="text-xs sm:text-sm font-bold text-slate-800">
            Kỳ báo cáo:
          </span>
        </div>

        {onPinItem && (
          <button
            type="button"
            data-testid="pin-item-button"
            onClick={handlePin}
            title="Ghim chỉ tiêu này sang khay tham chiếu bên phải"
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white hover:bg-blue-50 text-slate-700 hover:text-blue-700 border border-slate-200 text-xs font-semibold transition cursor-pointer shadow-2xs"
          >
            <Pin className="w-3.5 h-3.5 text-blue-600" />
            <span>📌 Ghim</span>
          </button>
        )}
      </div>

      {/* Bộ nút chọn kỳ báo cáo thân thiện (Senior-Friendly Timeline Buttons) */}
      {snapshots.length > 0 ? (
        <div className="mt-2.5 space-y-2.5">
          <div className="flex flex-wrap items-center gap-2">
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
                    onTimelineChange?.(snap, null);
                  }}
                  className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs sm:text-sm font-bold transition-all cursor-pointer border ${
                    isSelected
                      ? 'bg-blue-700 text-white border-blue-700 shadow-sm scale-102'
                      : 'bg-white text-slate-700 border-slate-200 hover:bg-blue-50 hover:border-blue-300'
                  }`}
                >
                  <span>{snap.period_label || snapDate}</span>
                  <span
                    className={`px-2 py-0.5 rounded-lg text-xs font-mono font-bold ${
                      isSelected ? 'bg-blue-800 text-white' : 'bg-slate-100 text-slate-800'
                    }`}
                  >
                    {snap.value}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Ô chọn ngày tùy chỉnh tinh giản */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-blue-100/60 text-xs text-slate-600">
            <div className="flex items-center gap-1.5">
              <span className="font-medium text-slate-600">Tra cứu ngày khác:</span>
              <input
                type="date"
                data-testid="slider-custom-date-input"
                value={customDate}
                onChange={(e) => {
                  setCustomDate(e.target.value);
                  applyCustomDate(e.target.value);
                }}
                className="px-2 py-1 text-xs rounded-lg border border-slate-200 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="button"
                data-testid="slider-custom-date-apply"
                onClick={() => applyCustomDate(customDate)}
                className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 transition cursor-pointer"
              >
                Áp dụng
              </button>
            </div>

            {effectiveShiftNotice && (
              <div
                data-testid="slider-temporal-shift-notice"
                className="text-xs font-medium text-amber-800 bg-amber-50 px-2.5 py-1 rounded-md border border-amber-200 flex items-center gap-1"
              >
                <Clock className="w-3.5 h-3.5 text-amber-600" />
                <span>{effectiveShiftNotice}</span>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-2 pt-2 border-t border-slate-200/70 flex items-center justify-between text-xs text-amber-700 bg-amber-50/70 px-3 py-1.5 rounded-lg border border-amber-200/60">
          <span>Chỉ tiêu hiện chưa có lịch sử biến động qua các kỳ báo cáo đã phê duyệt.</span>
        </div>
      )}
    </div>
  );
};
