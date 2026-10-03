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

  return (
    <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-slate-800/60 space-y-2">
      <div className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold tracking-wide">
        <Sparkles className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
        <span>Gợi ý câu hỏi liên quan tiếp theo:</span>
      </div>
      <div className="flex flex-wrap gap-2">
        {chips.map((chip) => (
          <button
            key={chip.id}
            onClick={() => onSelect(chip.query_text)}
            className="group flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-blue-50/80 hover:bg-blue-100 text-blue-700 hover:text-blue-800 border border-blue-200/80 hover:border-blue-300 transition-all duration-150 hover:shadow-sm active:scale-95 text-left cursor-pointer"
            title={chip.query_text}
          >
            <span>{chip.label}</span>
            <ArrowRight className="w-3 h-3 opacity-50 group-hover:opacity-100 group-hover:translate-x-0.5 transition-all text-blue-600" />
          </button>
        ))}
      </div>
    </div>
  );
};

