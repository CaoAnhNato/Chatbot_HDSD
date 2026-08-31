'use client';

import React from 'react';
import { X } from 'lucide-react';
import { resolveImageUrl } from '@/lib/utils';

interface MediaViewerProps {
  isOpen: boolean;
  imageUrl: string | null;
  altText?: string;
  onClose: () => void;
}

export const MediaViewer: React.FC<MediaViewerProps> = ({
  isOpen,
  imageUrl,
  altText = 'Ảnh chụp giao diện',
  onClose,
}) => {
  if (!isOpen || !imageUrl) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative max-w-5xl max-h-[90vh] bg-white rounded-2xl overflow-hidden shadow-2xl border border-slate-200">
        <div className="flex items-center justify-between px-5 py-3.5 bg-slate-50 border-b border-slate-200">
          <span className="text-sm font-semibold text-slate-800">{altText}</span>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-900 hover:bg-slate-200 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 flex items-center justify-center overflow-auto max-h-[calc(90vh-60px)] bg-slate-100/50">
          <img
            src={resolveImageUrl(imageUrl)}
            alt={altText}
            className="max-h-full max-w-full object-contain rounded-xl shadow-md bg-white border border-slate-200"
          />
        </div>
      </div>
    </div>
  );
};
