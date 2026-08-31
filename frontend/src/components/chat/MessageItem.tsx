'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage } from '@/types/chat';
import { User, Bot, ExternalLink, ZoomIn } from 'lucide-react';
import { YouTubeEmbed } from './YouTubeEmbed';
import { ContactCard } from './ContactCard';
import { QuickActionChips } from './QuickActionChips';
import { resolveImageUrl } from '@/lib/utils';

interface MessageItemProps {
  message: ChatMessage;
  onImageClick: (imageUrl: string, altText: string) => void;
  onSelectChip?: (queryText: string) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onImageClick,
  onSelectChip,
}) => {
  const isUser = message.role === 'user';

  // Process placeholder tags [IMAGE_N] and [VIDEO] with metadata
  const processedContent = React.useMemo(() => {
    if (!message.content) return '';
    let text = message.content;

    // 1. Map [IMAGE_N] to markdown images from metadata.images
    if (message.images && message.images.length > 0) {
      text = text.replace(/\[IMAGE_(\d+)\]/g, (match, idxStr) => {
        const idx = parseInt(idxStr, 10) - 1;
        if (idx >= 0 && idx < message.images!.length) {
          const imgUrl = resolveImageUrl(message.images![idx]);
          return `\n\n![Ảnh minh họa ${idx + 1}](${imgUrl})\n\n`;
        }
        return '';
      });
    }

    // 2. Map [VIDEO] to video markdown embed from metadata.youtube_links
    if (message.youtube_links && message.youtube_links.length > 0) {
      text = text.replace(/\[VIDEO\]/g, () => {
        const url = message.youtube_links![0];
        return `\n\n📺 **Xem video hướng dẫn chi tiết:** [Bấm vào đây để xem video (thời gian 00:00)](${url})\n\n`;
      });
    }

    return text;
  }, [message.content, message.images, message.youtube_links]);

  return (
    <div className={`flex gap-3 my-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div
        className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-sm ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-indigo-50 text-indigo-600 border border-indigo-100'
        }`}
      >
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-5 h-5" />}
      </div>

      <div
        className={`max-w-[85%] rounded-2xl px-5 py-3.5 text-[15px] shadow-sm leading-relaxed ${
          isUser
            ? 'bg-blue-600 text-white rounded-tr-none'
            : 'bg-slate-50 text-slate-800 border border-slate-200/80 rounded-tl-none'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-slate prose-base max-w-none space-y-2 text-slate-800 text-[15px]">
            {message.contact_support && <ContactCard info={message.contact_support} />}

            {message.content ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  img: ({ node, src, alt, ...props }) => {
                    const finalSrc = resolveImageUrl(src || '');
                    return (
                      <div className="my-3 relative group rounded-xl overflow-hidden border border-slate-200 bg-white shadow-sm inline-block max-w-full hover:shadow-md transition">
                        <img
                          src={finalSrc}
                          alt={alt || 'UI Preview'}
                          className="max-h-80 w-auto object-contain cursor-pointer transition-transform group-hover:scale-[1.01]"
                          onClick={() => finalSrc && onImageClick(finalSrc, alt || 'Ảnh minh họa')}
                          loading="lazy"
                          {...props}
                        />
                        <button
                          onClick={() => finalSrc && onImageClick(finalSrc, alt || 'Ảnh minh họa')}
                          className="absolute bottom-2.5 right-2.5 bg-slate-900/80 hover:bg-slate-900 text-white p-2 rounded-lg opacity-0 group-hover:opacity-100 transition shadow-md"
                          title="Xem phóng to"
                        >
                          <ZoomIn className="w-4 h-4" />
                        </button>
                      </div>
                    );
                  },
                  a: ({ node, href, children, ...props }) => {
                    const isYouTube = href && (href.includes('youtube.com') || href.includes('youtu.be'));
                    if (isYouTube && href) {
                      return (
                        <div className="not-prose my-3">
                          <YouTubeEmbed url={href} />
                          <a
                            href={href}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mt-1 font-medium"
                          >
                            <span>{children}</span>
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      );
                    }
                    return (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-600 font-medium underline hover:text-blue-700 inline-flex items-center gap-0.5"
                        {...props}
                      >
                        {children}
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    );
                  },
                }}
              >
                {processedContent}
              </ReactMarkdown>
            ) : (
              <div className="flex items-center gap-2 py-1 text-slate-500">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse"></span>
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse delay-150"></span>
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse delay-300"></span>
                <span className="text-xs ml-1 text-slate-500 font-medium">Đang tra cứu tài liệu HDSD...</span>
              </div>
            )}

            {message.quick_action_chips && onSelectChip && (
              <QuickActionChips chips={message.quick_action_chips} onSelect={onSelectChip} />
            )}
          </div>
        )}
        <div
          suppressHydrationWarning
          className={`text-[11px] mt-1.5 font-medium ${
            isUser ? 'text-blue-100 text-right' : 'text-slate-400 text-left'
          }`}
        >
          {new Date(message.timestamp).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', hour12: false })}
        </div>
      </div>
    </div>
  );
};
