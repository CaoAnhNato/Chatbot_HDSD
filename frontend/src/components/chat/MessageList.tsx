'use client';

import React, { useEffect, useRef } from 'react';
import { ChatMessage } from '@/types/chat';
import { MessageItem } from './MessageItem';
import { Bot } from 'lucide-react';

interface MessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  onImageClick: (imageUrl: string, altText: string) => void;
  onSelectChip?: (queryText: string) => void;
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  onImageClick,
  onSelectChip,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-white">
      {messages.length === 0 ? (
        <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500">
          <div className="w-16 h-16 bg-blue-50 text-blue-600 rounded-2xl flex items-center justify-center mb-4 border border-blue-100 shadow-sm">
            <Bot className="w-8 h-8" />
          </div>
          <h3 className="text-lg font-bold text-slate-800 mb-1.5">
            Trợ lý AI Hướng dẫn Sử dụng Hệ thống
          </h3>
          <p className="text-[15px] max-w-md text-slate-500 leading-relaxed">
            Hỗ trợ tra cứu quy trình, hướng dẫn từng bước thao tác phần mềm kèm ảnh chụp màn hình UI và video minh họa chi tiết.
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

      {isLoading && (!messages.length || messages[messages.length - 1].role === 'user') && (
        <div className="flex items-center gap-3 my-4">
          <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center animate-pulse shadow-sm">
            <Bot className="w-5 h-5" />
          </div>
          <div className="bg-slate-50 border border-slate-200/80 rounded-2xl rounded-tl-none px-4 py-3 text-[14px] text-slate-500 flex items-center gap-2 shadow-sm">
            <span className="inline-block w-2 h-2 rounded-full bg-blue-600 animate-bounce" />
            <span className="inline-block w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.2s]" />
            <span className="inline-block w-2 h-2 rounded-full bg-blue-600 animate-bounce [animation-delay:0.4s]" />
            <span className="ml-1 text-[13px] font-medium">Đang tra cứu tài liệu HDSD...</span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
