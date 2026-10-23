'use client';

import React from 'react';
import { QuickActionChip } from '@/types/chat';
import { Sparkles, ArrowRight } from 'lucide-react';

interface QuickActionChipsProps {
  chips: QuickActionChip[];
  onSelect: (queryText: string) => void;
}

export const QuickActionChips: React.FC<QuickActionChipsProps> = ({ chips, onSelect }) => {
  if (!chips || chips.length === 0) return null;

  const isChildCriterionSelection = chips.some(
    (c) => c.id?.startsWith('chip_alt_') || c.label?.startsWith('🔘')
  );

  return (
    <div
      className={
        isChildCriterionSelection
          ? 'my-2.5 not-prose'
          : 'mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/60 space-y-2 not-prose'
      }
    >
      {!isChildCriterionSelection && (
        <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold tracking-wide">
          <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
          <span>Gợi ý câu hỏi liên quan tiếp theo:</span>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => {
          const hasPreviewVal =
            chip.preview_value !== undefined &&
            chip.preview_value !== null &&
            String(chip.preview_value).trim() !== '' &&
            String(chip.preview_value).trim() !== '-';
          const childCnt = typeof chip.child_count === 'number' ? chip.child_count : 0;
          const isGroup = Boolean(chip.is_parent_group || childCnt > 0);
          const isEnriched =
            hasPreviewVal || isGroup || Boolean(chip.unit_or_status);

          return (
            <button
              key={chip.id}
              data-testid={isEnriched ? `value-preview-chip-${chip.id}` : `quick-chip-${chip.id}`}
              onClick={() => onSelect(chip.query_text)}
              className="group flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium bg-blue-50/80 hover:bg-blue-100 text-blue-700 hover:text-blue-800 border border-blue-200/80 hover:border-blue-300 transition-all duration-150 hover:shadow-sm active:scale-95 text-left cursor-pointer"
              title={chip.query_text}
            >
              <span>{chip.label}</span>
              {hasPreviewVal && (
                <span
                  data-testid="chip-preview-badge"
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-300 shadow-2xs"
                >
                  <span>[{String(chip.preview_value)}]</span>
                  {isGroup && childCnt > 0 && (
                    <span
                      data-testid="chip-group-badge"
                      className="text-[10px] font-semibold text-indigo-700"
                    >
                      • {childCnt} chỉ tiêu con ▸
                    </span>
                  )}
                </span>
              )}
              {!hasPreviewVal && isGroup && childCnt > 0 && (
                <span
                  data-testid="chip-group-badge"
                  className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-indigo-100 text-indigo-800 border border-indigo-300 shadow-2xs"
                >
                  [{childCnt} chỉ tiêu con ▸]
                </span>
              )}
              {!hasPreviewVal && !isGroup && chip.unit_or_status && (
                <span
                  data-testid="chip-status-badge"
                  className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-50 text-amber-700 border border-amber-200"
                >
                  [{chip.unit_or_status}]
                </span>
              )}
              <ArrowRight className="w-3 h-3 opacity-50 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all text-blue-600" />
            </button>
          );
        })}
      </div>
    </div>
  );
};


