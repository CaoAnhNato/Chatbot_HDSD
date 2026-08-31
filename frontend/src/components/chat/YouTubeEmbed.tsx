'use client';

import React from 'react';
import { PlayCircle } from 'lucide-react';

interface YouTubeEmbedProps {
  url: string;
}

export const YouTubeEmbed: React.FC<YouTubeEmbedProps> = ({ url }) => {
  // Extract YouTube ID & start timestamp
  const getEmbedUrl = (rawUrl: string): string => {
    let videoId = '';
    let start = 0;

    const tMatch = rawUrl.match(/[?&]t=(\d+)s?/);
    if (tMatch) {
      start = parseInt(tMatch[1], 10);
    }

    if (rawUrl.includes('youtu.be/')) {
      videoId = rawUrl.split('youtu.be/')[1].split('?')[0];
    } else if (rawUrl.includes('youtube.com/watch')) {
      const vMatch = rawUrl.match(/[?&]v=([^&]+)/);
      if (vMatch) videoId = vMatch[1];
    }

    if (!videoId) return rawUrl;
    return `https://www.youtube.com/embed/${videoId}?start=${start}&autoplay=0`;
  };

  const embedUrl = getEmbedUrl(url);

  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700 bg-slate-900 shadow-md">
      <div className="flex items-center gap-2 px-3 py-2 bg-slate-800 text-xs font-semibold text-red-400 border-b border-slate-700">
        <PlayCircle className="w-4 h-4" />
        <span>Video Hướng dẫn Thao tác</span>
      </div>
      <div className="relative aspect-video w-full">
        <iframe
          src={embedUrl}
          title="YouTube video player"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          className="absolute inset-0 w-full h-full border-0"
        />
      </div>
    </div>
  );
};
