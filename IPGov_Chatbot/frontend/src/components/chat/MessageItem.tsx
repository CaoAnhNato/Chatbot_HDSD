'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage, PinnedDrawerItem, TimelineSnapshotItem } from '@/types/chat';
import { User, Bot, ExternalLink, ZoomIn, ChevronRight, Copy, Check, Terminal } from 'lucide-react';
import { YouTubeEmbed } from './YouTubeEmbed';
import { ContactCard } from './ContactCard';
import { QuickActionChips } from './QuickActionChips';
import { SmartTable } from './SmartTable';
import { SingleMetricSliderCard } from './SingleMetricSliderCard';
import { FluidTextStream } from './FluidTextStream';
import { resolveImageUrl } from '@/lib/utils';
import { normalizeMarkdownTables } from '@/lib/table_normalizer';

interface MessageItemProps {
  message: ChatMessage;
  onImageClick: (imageUrl: string, altText: string) => void;
  onSelectChip?: (queryText: string) => void;
  onPinItem?: (item: PinnedDrawerItem) => void;
}

const CollapsibleSqlBlock: React.FC<{ summary: string; content: string }> = ({ summary, content }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const [copied, setCopied] = React.useState(false);

  // Extract clean SQL from ```sql ... ``` or raw text
  const cleanSql = React.useMemo(() => {
    const codeMatch = content.match(/```(?:sql)?\s*([\s\S]*?)\s*```/);
    return codeMatch ? codeMatch[1].trim() : content.trim();
  }, [content]);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(cleanSql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="my-3 rounded-xl border border-slate-700/80 bg-slate-900 overflow-hidden shadow-sm not-prose transition">
      <div
        onClick={() => setIsOpen(!isOpen)}
        className="cursor-pointer select-none px-4 py-2.5 flex items-center justify-between bg-slate-800 hover:bg-slate-750 text-slate-200 text-xs font-medium transition"
      >
        <div className="flex items-center gap-2">
          <ChevronRight
            className={`w-3.5 h-3.5 transform transition-transform text-slate-400 ${
              isOpen ? 'rotate-90 text-blue-400' : ''
            }`}
          />
          <Terminal className="w-3.5 h-3.5 text-blue-400" />
          <span className="font-semibold text-slate-100">
            {summary.trim() || '🔍 Xem câu lệnh truy vấn (SQL Query)'}
          </span>
        </div>
        <button
          onClick={handleCopy}
          type="button"
          className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-[11px] flex items-center gap-1 transition shadow-sm"
          title="Sao chép câu SQL"
        >
          {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
          <span>{copied ? 'Đã chép' : 'Sao chép'}</span>
        </button>
      </div>
      {isOpen && (
        <div className="p-3.5 bg-slate-950 font-mono text-[12px] text-emerald-400 overflow-x-auto border-t border-slate-800 whitespace-pre-wrap leading-relaxed">
          {cleanSql}
        </div>
      )}
    </div>
  );
};

const MessageItemComponent: React.FC<MessageItemProps> = ({
  message,
  onImageClick,
  onSelectChip,
  onPinItem,
}) => {
  const isUser = message.role === 'user';

  // [R2.4] Timeline snapshot & temporal shift notice state for 0ms reactive sync
  const [activeSnapshot, setActiveSnapshot] = React.useState<TimelineSnapshotItem | null>(null);
  const [activeShiftNotice, setActiveShiftNotice] = React.useState<string | null>(null);

  React.useEffect(() => {
    setActiveSnapshot(null);
    setActiveShiftNotice(null);
  }, [message.id]);

  // Animation settlement state: if message is not streaming when mounted (e.g. historical messages),
  // it is settled immediately. If streaming, it stays active until FluidTextStream drains completely.
  const [isAnimationSettled, setIsAnimationSettled] = React.useState(!message.isStreaming);

  // Process placeholder tags [IMAGE_N] and [VIDEO] with metadata and normalize markdown tables
  const processedContent = React.useMemo(() => {
    if (!message.content) return '';
    let text = normalizeMarkdownTables(message.content);

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

    // [R2.3] KHỬ TRÙNG LẶP NÚT GỢI Ý CHỈ TIÊU CON TRONG ĐOẠN VĂN:
    // Loại bỏ hoàn toàn dòng danh sách văn bản thô "🔘 [Tên chỉ tiêu con]..."
    // để chỉ tiêu con CHỈ xuất hiện DUY NHẤT một lần dạng nút bấm QuickActionChips ở đáy
    text = text.replace(/(?:\r?\n\s*)*\r?\n*(?:[-*]\s*)?(?:🔘\s*`?\[[^\]\r\n]+\]`?\s*)+$/gm, '');
    text = text.replace(/\r?\n*\s*(?:[-*]\s*)?(?:🔘\s*`?\[[^\]\r\n]+\]`?\s*)+(?=\r?\n|$)/g, '');

    // [R2.4] ĐỒNG BỘ PHẢN ỨNG 0MS THẺ 5 TRƯỜNG KHI CHUYỂN KỲ BÁO CÁO:
    if (activeSnapshot) {
      const targetVal = String(activeSnapshot.value || '').trim();
      const targetDate = String(activeSnapshot.report_date || activeSnapshot.date || '').trim();

      // Đồng bộ trường Giá trị
      text = text.replace(
        /(- \*\*Giá trị:\*\* )[^\n]+/,
        `$1${targetVal}`
      );
      // Đồng bộ trường Thời điểm báo cáo
      text = text.replace(
        /(- \*\*Thời điểm báo cáo:\*\* )[^\n]+/,
        `$1${targetDate}`
      );
      // Đồng bộ trường Đơn vị thực hiện nếu snapshot có đơn vị khác
      if (activeSnapshot.office) {
        text = text.replace(
          /(- \*\*Đơn vị thực hiện:\*\* )[^\n]+/,
          `$1${activeSnapshot.office}`
        );
      }
      // Đồng bộ lưu ý mốc thời gian nếu có cảnh báo lệch ngày
      if (activeShiftNotice) {
        if (text.includes('- **Lưu ý mốc thời gian:**')) {
          text = text.replace(
            /(- \*\*Lưu ý mốc thời gian:\*\* )[^\n]+/,
            `$1${activeShiftNotice}`
          );
        } else {
          text = text.replace(
            /(- \*\*Thời điểm báo cáo:\*\* [^\n]+)/,
            `$1\n- **Lưu ý mốc thời gian:** ${activeShiftNotice}`
          );
        }
      } else {
        text = text.replace(/\n- \*\*Lưu ý mốc thời gian:\*\* [^\n]+/, '');
      }
    }

    return text;
  }, [message.content, message.images, message.youtube_links, activeSnapshot, activeShiftNotice]);

  // [R2.4] Đồng bộ huy hiệu preview_value trên QuickActionChips theo kỳ đang chọn (0ms Client-side)
  const reactiveChips = React.useMemo(() => {
    if (!message.quick_action_chips || message.quick_action_chips.length === 0) return [];
    if (!activeSnapshot) return message.quick_action_chips;

    const snapDate = activeSnapshot.report_date || activeSnapshot.date;
    const childVals = (activeSnapshot as any)?.child_values || {};

    return message.quick_action_chips.map((chip) => {
      let nextPreviewVal = chip.preview_value;
      const cleanName = chip.label.replace(/^🔘\s*\[?|\]?$/g, '').trim();

      // Đối chiếu theo id hoặc tên chỉ tiêu con trong snapshot
      if (childVals[chip.id] !== undefined) {
        nextPreviewVal = String(childVals[chip.id]);
      } else if (childVals[cleanName] !== undefined) {
        nextPreviewVal = String(childVals[cleanName]);
      } else if ((chip as any).timeline_values && snapDate && (chip as any).timeline_values[snapDate] !== undefined) {
        nextPreviewVal = String((chip as any).timeline_values[snapDate]);
      }

      return {
        ...chip,
        preview_value: nextPreviewVal,
      };
    });
  }, [message.quick_action_chips, activeSnapshot]);

  // Parse markdown vs <details> collapsible blocks
  const contentSegments = React.useMemo(() => {
    if (!processedContent) return [];
    const detailsRegex = /<details[^>]*>[\s\r\n]*<summary[^>]*>([\s\S]*?)<\/summary>([\s\S]*?)<\/details>/gi;
    const segs: Array<{ type: 'markdown' | 'details'; content: string; summary?: string }> = [];
    let lastIdx = 0;
    let match: RegExpExecArray | null;

    while ((match = detailsRegex.exec(processedContent)) !== null) {
      if (match.index > lastIdx) {
        segs.push({
          type: 'markdown',
          content: processedContent.slice(lastIdx, match.index),
        });
      }
      segs.push({
        type: 'details',
        summary: match[1].trim(),
        content: match[2].trim(),
      });
      lastIdx = match.index + match[0].length;
    }

    if (lastIdx < processedContent.length) {
      segs.push({
        type: 'markdown',
        content: processedContent.slice(lastIdx),
      });
    }

    return segs;
  }, [processedContent]);

  const markdownComponents = React.useMemo(
    () => ({
      table: ({ node, children, ...props }: any) => {
        return (
          <SmartTable
            tabularData={message.tabular_data}
            onSelectChip={onSelectChip}
            onPinItem={onPinItem}
          >
            {children}
          </SmartTable>
        );
      },
      img: ({ node, src, alt, ...props }: any) => {
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
      a: ({ node, href, children, ...props }: any) => {
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
    }),
    [message.tabular_data, onImageClick, onSelectChip, onPinItem]
  );

  // R1.1: Tránh hiển thị trùng lặp icon reasoning khi đang streaming và chưa có nội dung
  if (!isUser && message.isStreaming && !message.content) {
    return null;
  }

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
          <p className="whitespace-pre-wrap">
            {message.content.replace(/^\[tenant_code=[^\]]+\]\s*/i, '').trim()}
          </p>
        ) : (
          <div className="prose prose-slate prose-base max-w-none space-y-2 text-slate-800 text-[15px]">
            {message.contact_support && <ContactCard info={message.contact_support} />}

            {/* Feature 4: Senior-Friendly timeline control bar cho chỉ tiêu đơn lẻ REQ-Q02 / SC-2.4a */}
            {message.tabular_data?.single_metric_card && (
              <SingleMetricSliderCard
                card={message.tabular_data.single_metric_card}
                onSelectChip={onSelectChip}
                onPinItem={onPinItem}
                onTimelineChange={(snapshot, shiftNotice) => {
                  setActiveSnapshot(snapshot);
                  setActiveShiftNotice(shiftNotice);
                }}
              />
            )}

            {message.content ? (
              !isAnimationSettled ? (
                <FluidTextStream
                  content={processedContent}
                  isStreaming={Boolean(message.isStreaming)}
                  components={markdownComponents}
                  onSettled={() => setIsAnimationSettled(true)}
                />
              ) : (
                contentSegments.map((seg, idx) =>
                  seg.type === 'details' ? (
                    <React.Fragment key={`details-${idx}`}>
                      {reactiveChips &&
                        reactiveChips.length > 0 &&
                        onSelectChip &&
                        reactiveChips.some(
                          (c) => c.id?.startsWith('chip_alt_') || c.label?.startsWith('🔘')
                        ) && (
                          <QuickActionChips
                            chips={reactiveChips}
                            onSelect={onSelectChip}
                          />
                        )}
                      <CollapsibleSqlBlock
                        summary={seg.summary || '🔍 Xem câu lệnh truy vấn (SQL Query)'}
                        content={seg.content}
                      />
                    </React.Fragment>
                  ) : (
                    <ReactMarkdown
                      key={`md-${idx}`}
                      remarkPlugins={[remarkGfm]}
                      components={markdownComponents}
                    >
                      {seg.content}
                    </ReactMarkdown>
                  )
                )
              )
            ) : (!message.isStreaming && !message.contact_support) ? (
              <div className="flex items-center gap-2 py-1 text-slate-500">
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse"></span>
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse delay-150"></span>
                <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse delay-300"></span>
                <span className="text-xs ml-1 text-slate-500 font-medium">Đang tra cứu dữ liệu...</span>
              </div>
            ) : null}

            {reactiveChips &&
              reactiveChips.length > 0 &&
              onSelectChip &&
              !(
                isAnimationSettled &&
                contentSegments.some((s) => s.type === 'details') &&
                reactiveChips.some(
                  (c) => c.id?.startsWith('chip_alt_') || c.label?.startsWith('🔘')
                )
              ) && (
                <QuickActionChips chips={reactiveChips} onSelect={onSelectChip} />
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

export const MessageItem = React.memo(MessageItemComponent, (prev, next) => {
  return (
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.message.isStreaming === next.message.isStreaming &&
    prev.message.tabular_data === next.message.tabular_data &&
    prev.message.contact_support === next.message.contact_support &&
    prev.message.quick_action_chips === next.message.quick_action_chips &&
    prev.onImageClick === next.onImageClick &&
    prev.onSelectChip === next.onSelectChip &&
    prev.onPinItem === next.onPinItem
  );
});
MessageItem.displayName = 'MessageItem';

