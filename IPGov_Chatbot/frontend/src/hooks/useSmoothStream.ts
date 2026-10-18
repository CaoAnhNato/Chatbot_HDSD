import { useState, useEffect, useRef, useCallback } from 'react';

interface UseSmoothStreamOptions {
  /**
   * Base interval between character drains in milliseconds.
   * Default: 35ms (approx 30 characters/sec for a natural human reading flow)
   */
  baseCharInterval?: number;
  /**
   * Word count for active GPU animation tail window.
   * Default: 4 words (O(1) constant GPU compositor layer count)
   */
  tailWordCount?: number;
  /**
   * Optional callback when the stream has finished and the queue is completely drained.
   */
  onSettled?: () => void;
}

interface UseSmoothStreamResult {
  displayedText: string;
  settledHead: string;
  tailWords: Array<{ id: string; text: string }>;
  isAnimating: boolean;
  skipAnimation: () => void;
}

/**
 * High-Performance Smooth Token Stream Hook
 * - Decouples SSE network jitter from UI rendering via FIFO queue + continuous RAF clock
 * - Implements Graceful Queue Drain Completion (~35ms-40ms pace)
 * - Ephemeral sliding window of at most `tailWordCount` words for O(1) GPU layers
 * - Instant flush on Escape key, click, tab visibility change, or stream completion
 */
export function useSmoothStream(
  rawContent: string,
  isStreaming: boolean,
  options: UseSmoothStreamOptions = {}
): UseSmoothStreamResult {
  const { baseCharInterval = 35, tailWordCount = 4, onSettled } = options;

  const [displayedText, setDisplayedText] = useState(rawContent || '');
  const [isAnimating, setIsAnimating] = useState(false);

  // References to decouple state from high-frequency RAF loop
  const targetTextRef = useRef(rawContent);
  targetTextRef.current = rawContent;

  const displayedTextRef = useRef(rawContent || '');
  const rafIdRef = useRef<number | null>(null);
  const lastTickRef = useRef<number>(0);
  const isStreamingRef = useRef(isStreaming);
  isStreamingRef.current = isStreaming;
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled;

  // Immediate flush / skip animation function
  const skipAnimation = useCallback(() => {
    displayedTextRef.current = targetTextRef.current;
    setDisplayedText(targetTextRef.current);
    setIsAnimating(false);
    if (rafIdRef.current) {
      cancelAnimationFrame(rafIdRef.current);
      rafIdRef.current = null;
    }
    lastTickRef.current = 0;
    onSettledRef.current?.();
  }, []);

  // Update target and manage continuous RAF loop
  useEffect(() => {
    // If rawContent was reset or cleared, sync immediately
    if (rawContent.length < displayedTextRef.current.length) {
      displayedTextRef.current = rawContent;
      setDisplayedText(rawContent);
    }

    // If completely finished and already displayed 100%, settle immediately
    if (!isStreaming && displayedTextRef.current.length >= rawContent.length) {
      setIsAnimating(false);
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      lastTickRef.current = 0;
      onSettledRef.current?.();
      return;
    }

    // Start animating if there is pending text or actively streaming
    setIsAnimating(true);

    const tick = (now: number) => {
      const target = targetTextRef.current;
      const current = displayedTextRef.current;

      if (current.length < target.length) {
        const backlog = target.length - current.length;

        // Graceful Queue Drain Pacing:
        // Maintain a natural, comfortable reading cadence (~35ms-40ms per step)
        // Dynamically scale charsToDrain to prevent lag accumulation while avoiding abrupt snaps.
        let charsToDrain = 1;
        if (backlog > 150) {
          charsToDrain = Math.min(backlog, Math.ceil(backlog / 25));
        } else if (backlog > 60) {
          charsToDrain = 3;
        } else if (backlog > 20) {
          charsToDrain = 2;
        }

        if (lastTickRef.current === 0) {
          lastTickRef.current = now;
        }
        const elapsed = now - lastTickRef.current;

        if (elapsed >= baseCharInterval) {
          lastTickRef.current = now;
          const nextLength = Math.min(target.length, current.length + charsToDrain);
          const nextText = target.slice(0, nextLength);
          displayedTextRef.current = nextText;
          setDisplayedText(nextText);
        }

        rafIdRef.current = requestAnimationFrame(tick);
      } else {
        // Queue has caught up with target
        if (!isStreamingRef.current) {
          // Network is done and queue is fully drained -> settle cleanly
          setIsAnimating(false);
          rafIdRef.current = null;
          lastTickRef.current = 0;
          onSettledRef.current?.();
        } else {
          // Actively streaming, await next network chunk
          rafIdRef.current = requestAnimationFrame(tick);
        }
      }
    };

    if (!rafIdRef.current) {
      lastTickRef.current = performance.now();
      rafIdRef.current = requestAnimationFrame(tick);
    }
  }, [rawContent, isStreaming, baseCharInterval]);

  // Clean up RAF on unmount
  useEffect(() => {
    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
    };
  }, []);

  // Instant flush when user presses Escape or switches tab to prevent buffer lag
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden && isAnimating) {
        skipAnimation();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isAnimating) {
        skipAnimation();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isAnimating, skipAnimation]);

  // Compute settledHead vs decaying tail words
  // Only settle when animation is completely finished (isAnimating === false)
  if (!isAnimating) {
    return {
      displayedText,
      settledHead: displayedText,
      tailWords: [],
      isAnimating: false,
      skipAnimation,
    };
  }

  // Tokenize the trailing active section for sliding window reveal
  // Split the last N words into animated tokens, leave the rest settled
  const trimmed = displayedText;
  const lastSpaceIndexes: number[] = [];
  for (let i = trimmed.length - 1; i >= 0 && lastSpaceIndexes.length < tailWordCount; i--) {
    if (trimmed[i] === ' ' || trimmed[i] === '\n') {
      lastSpaceIndexes.push(i);
    }
  }

  const splitIndex = lastSpaceIndexes.length > 0 ? lastSpaceIndexes[lastSpaceIndexes.length - 1] : 0;
  const settledHead = trimmed.slice(0, splitIndex);
  const tailRaw = trimmed.slice(splitIndex);

  // Split tailRaw into words preserving spaces
  const rawParts = tailRaw.split(/(\s+)/).filter(Boolean);
  const tailWords = rawParts.map((part, idx) => ({
    id: `tail-${splitIndex}-${idx}-${part}`,
    text: part,
  }));

  return {
    displayedText,
    settledHead,
    tailWords,
    isAnimating,
    skipAnimation,
  };
}
