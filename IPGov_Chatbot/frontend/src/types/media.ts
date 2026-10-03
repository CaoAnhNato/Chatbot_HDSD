export interface YouTubeVideoInfo {
  video_url: string;
  timestamp_start: number;
  timestamp_end?: number;
  display_link: string;
  title?: string;
}

export interface MediaViewerState {
  isOpen: boolean;
  imageUrl: string | null;
  altText: string;
}
