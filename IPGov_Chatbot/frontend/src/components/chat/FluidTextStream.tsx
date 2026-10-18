import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSmoothStream } from '@/hooks/useSmoothStream';

interface FluidTextStreamProps {
  content: string;
  isStreaming: boolean;
  components?: any;
  onSettled?: () => void;
}

/**
 * Memoized settled markdown block
 * Skips AST re-parsing when new characters arrive in active tail
 */
const MemoizedMarkdownBlock = React.memo<{
  content: string;
  components?: any;
}>(
  ({ content, components }) => {
    if (!content.trim()) return null;
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    );
  },
  (prev, next) => prev.content === next.content
);
MemoizedMarkdownBlock.displayName = 'MemoizedMarkdownBlock';

/**
 * FluidTextStream Component
 * Provides Google Gemini-like fluid text reveal with O(1) GPU Compositing
 * and O(1) Markdown AST re-parsing cost.
 */
export const FluidTextStream: React.FC<FluidTextStreamProps> = ({
  content,
  isStreaming,
  components,
  onSettled,
}) => {
  // Detect the start of the Warehouse Output Block (Markdown table, structured metric card, or <details> SQL block)
  // Only stream the introductory narrative text before the warehouse block; once finished (or immediately if none),
  // settle and render the full warehouse output immediately without character-by-character ms delay.
  const warehouseBlockIdx = React.useMemo(() => {
    if (!content) return -1;
    const candidates: number[] = [];
    if (content.trimStart().startsWith('|')) {
      candidates.push(0);
    }
    const tableIdx = content.indexOf('\n|');
    if (tableIdx !== -1) candidates.push(tableIdx);
    const cardIdx = content.indexOf('- **Chỉ tiêu:**');
    if (cardIdx !== -1) candidates.push(cardIdx);
    const parentCardIdx = content.indexOf('- **Nhóm chỉ tiêu cha:**');
    if (parentCardIdx !== -1) candidates.push(parentCardIdx);
    const detailsIdx = content.indexOf('<details');
    if (detailsIdx !== -1) candidates.push(detailsIdx);
    return candidates.length > 0 ? Math.min(...candidates) : -1;
  }, [content]);

  const streamableContent =
    warehouseBlockIdx !== -1 ? content.slice(0, warehouseBlockIdx).trimEnd() : content;

  const { displayedText, isAnimating, skipAnimation } = useSmoothStream(
    streamableContent,
    isStreaming,
    {
      baseCharInterval: 20,
      onSettled,
    }
  );

  React.useEffect(() => {
    if (!isStreaming && streamableContent.length === 0 && content.length > 0) {
      onSettled?.();
    }
  }, [isStreaming, streamableContent.length, content.length, onSettled]);

  // If streaming has finished and animation is settled, render standard markdown
  if (!isStreaming && (!isAnimating || streamableContent.length === 0)) {
    return (
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    );
  }

  // Split displayedText into completed blocks (ending with \n\n) vs active trailing block
  const lastDoubleNewline = displayedText.lastIndexOf('\n\n');
  const hasSettledBlocks = lastDoubleNewline !== -1;

  const settledContent = hasSettledBlocks
    ? displayedText.slice(0, lastDoubleNewline + 2)
    : '';
  const activeContent = hasSettledBlocks
    ? displayedText.slice(lastDoubleNewline + 2)
    : displayedText;

  // Split activeContent into settled head vs last 3-4 active words for sliding window reveal
  const words = activeContent.split(/(\s+)/);
  const tailWordThreshold = 4;
  const nonSpaceWordIndexes: number[] = [];

  for (let i = 0; i < words.length; i++) {
    if (words[i].trim().length > 0) {
      nonSpaceWordIndexes.push(i);
    }
  }

  let activeSplitIndex = 0;
  if (nonSpaceWordIndexes.length > tailWordThreshold) {
    const targetWordIndex =
      nonSpaceWordIndexes[nonSpaceWordIndexes.length - tailWordThreshold];
    activeSplitIndex = targetWordIndex;
  }

  const activeHead = words.slice(0, activeSplitIndex).join('');
  const activeTailWords = words.slice(activeSplitIndex);

  return (
    <div
      className={`fluid-stream-container ${isAnimating ? 'cursor-pointer select-text' : ''}`}
      onClick={isAnimating ? skipAnimation : undefined}
      title={isAnimating ? 'Bấm để hiển thị toàn bộ ngay lập tức (hoặc nhấn phím Esc)' : undefined}
    >
      {/* Settled Markdown Blocks (Memoized to prevent AST re-parse) */}
      {settledContent && (
        <div className="mb-2">
          <MemoizedMarkdownBlock content={settledContent} components={components} />
        </div>
      )}

      {/* Active Trailing Line with Sliding Window GPU Blur Reveal */}
      <div className="whitespace-pre-wrap leading-relaxed inline">
        {activeHead && <span>{activeHead}</span>}
        {activeTailWords.map((word, idx) => {
          const isSpace = /^\s+$/.test(word);
          if (isSpace) {
            return <span key={`tail-space-${idx}`}>{word}</span>;
          }
          return (
            <span
              key={`tail-word-${idx}-${word}`}
              className="fluid-token-reveal"
            >
              {word}
            </span>
          );
        })}

        {/* Pulsing subtle cursor while actively generating */}
        {isStreaming && (
          <span
            aria-hidden="true"
            className="inline-block w-1.5 h-4 ml-1 bg-blue-600/80 rounded-full animate-pulse align-middle"
          />
        )}
      </div>
    </div>
  );
};
