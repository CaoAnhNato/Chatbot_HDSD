'use client';

import React, { useEffect, useRef } from 'react';
import { ChatMessage } from '@/types/chat';
import { MessageItem } from './MessageItem';
import { Bot, Loader2 } from 'lucide-react';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  currentStage?: { stage: string; message: string } | null;
  onImageClick: (imageUrl: string, altText: string) => void;
  onSelectChip?: (queryText: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  currentStage,
  onImageClick,
  onSelectChip,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, currentStage]);

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-white">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
          <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-4 border border-blue-100 shadow-sm">
            <Bot className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-slate-800 mb-1.5">
            Trợ lý AI Tra Cứu Kho Dữ Liệu DWH & HDSD
          </h3>
          <p className="text-[15px] max-w-md text-slate-500 leading-relaxed">
            Hỗ trợ tra cứu tự hành trên kho dữ liệu điều hành chính quyền tỉnh và hướng dẫn quy trình nghiệp vụ thời gian thực.
          </p>
        </div>
      ) : (
        messages.map((msg) => (
          <MessageItem
            key={msg.id}
            message={msg}
            onImageClick={onImageClick}
            onSelectChip={onSelectChip}
          />
        ))
      )}

      {isLoading && (!messages.length || messages[messages.length - 1].role === 'user' || !messages[messages.length - 1].content) && (
        <div className="flex items-start gap-3 my-4 animate-in fade-in duration-200">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center shrink-0 shadow-sm">
            <Bot className="w-5 h-5 animate-pulse" />
          </div>
          <div className="bg-slate-50 border border-slate-200/90 rounded-2xl rounded-tl-none px-4 py-3 text-[14px] text-slate-700 shadow-sm space-y-1.5 min-w-[280px] max-w-md">
            <div className="flex items-center gap-2">
              <Loader2 className="w-4 h-4 text-blue-600 animate-spin shrink-0" />
              <span className="text-[13px] font-semibold text-slate-800">
                {currentStage?.message || 'Đang phân tích câu hỏi & đối chiếu ngữ cảnh...'}
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono">
              <span className="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-[10px] font-bold">
                {currentStage?.stage || 'THINKING'}
              </span>
              <span>•</span>
              <span>Thời gian thực</span>
            </div>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
