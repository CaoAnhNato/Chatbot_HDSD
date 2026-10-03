'use client';

import React from 'react';
import { PhoneCall, Clock, MessageSquareQuote } from 'lucide-react';
import { ContactSupportInfo } from '@/types/chat';

interface ContactCardProps {
  info?: ContactSupportInfo;
}

export const ContactCard: React.FC<ContactCardProps> = ({
  info = {
    title: "THÔNG TIN LIÊN HỆ HỖ TRỢ KỸ THUẬT (PHƯỜNG/XÃ)",
    working_hours: "Thứ 2 - Thứ 6 (Sáng: 07h30 – 11h30, Chiều: 13h00 – 17h00)",
    hotlines: ["028 3535 2524"],
  },
}) => {
  return (
    <div className="my-3 rounded-xl border border-amber-300 bg-amber-50/80 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-amber-900 font-semibold text-[15px] mb-3">
        <PhoneCall className="w-4 h-4 text-amber-700" />
        <span>{info.title}</span>
      </div>

      <div className="space-y-2 text-sm text-slate-700">
        <div className="flex items-start gap-2">
          <Clock className="w-4 h-4 text-slate-500 shrink-0 mt-0.5" />
          <span><strong>Thời gian:</strong> {info.working_hours}</span>
        </div>
        <div className="flex items-center gap-2">
          <PhoneCall className="w-4 h-4 text-emerald-600 shrink-0" />
          <span><strong>Hotline:</strong> {info.hotlines.join(" - ")}</span>
        </div>
        {info.zalo && (
          <div className="flex items-center gap-2">
            <MessageSquareQuote className="w-4 h-4 text-blue-600 shrink-0" />
            <span><strong>Zalo hỗ trợ:</strong> {info.zalo}</span>
          </div>
        )}
      </div>
    </div>
  );
};
