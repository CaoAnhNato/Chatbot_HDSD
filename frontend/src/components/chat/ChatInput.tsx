'use client';

import React, { useState } from 'react';
import { Send, Sparkles } from 'lucide-react';

interface ChatInputProps {
  onSendMessage: (query: string) => void;
  isLoading: boolean;
}

export const ChatInput: React.FC<ChatInputProps> = ({ onSendMessage, isLoading }) => {
  const [input, setInput] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    onSendMessage(input.trim());
    setInput('');
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-4 border-t border-slate-200 bg-white/95 backdrop-blur-md flex items-center gap-3 shrink-0"
    >
      <div className="relative flex-1">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Nhập câu hỏi thao tác (ví dụ: 'Làm thế nào để đăng ký tài khoản?')..."
          disabled={isLoading}
          className="w-full rounded-xl bg-slate-50 border border-slate-300 px-4 py-3.5 text-[15px] text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent focus:bg-white disabled:opacity-50 transition"
        />
        <Sparkles className="absolute right-4 top-4 w-4 h-4 text-slate-400 pointer-events-none" />
      </div>

      <button
        type="submit"
        disabled={!input.trim() || isLoading}
        className="rounded-xl bg-blue-600 hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-400 text-white px-6 py-3.5 text-[15px] font-medium flex items-center justify-center gap-2 transition-all shadow-sm active:scale-95 shrink-0"
      >
        <Send className="w-4 h-4" />
        <span className="hidden sm:inline">Gửi</span>
      </button>
    </form>
  );
};
