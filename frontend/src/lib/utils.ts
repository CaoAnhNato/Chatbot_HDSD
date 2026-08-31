import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function resolveImageUrl(url: string): string {
  if (!url) return '';
  
  const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://chatbothdsd-production.up.railway.app/api/v1';
  let backendOrigin = 'https://chatbothdsd-production.up.railway.app';
  try {
    const parsed = new URL(rawApiUrl);
    backendOrigin = parsed.origin;
  } catch {
    backendOrigin = 'https://chatbothdsd-production.up.railway.app';
  }

  let resolved = url.trim();

  // Replace localhost:8000 with current backend origin
  if (resolved.startsWith('http://localhost:8000') || resolved.startsWith('http://127.0.0.1:8000')) {
    resolved = resolved.replace(/^http:\/\/(localhost|127\.0\.0\.1):8000/, backendOrigin);
  } else if (resolved.startsWith('/static/')) {
    resolved = `${backendOrigin}${resolved}`;
  }

  // Force HTTPS if hosted on HTTPS
  if (typeof window !== 'undefined' && window.location.protocol === 'https:' && resolved.startsWith('http://')) {
    resolved = resolved.replace('http://', 'https://');
  }

  // Properly encode Unicode/Vietnamese filename characters for image fetching
  try {
    return encodeURI(decodeURI(resolved));
  } catch {
    return resolved;
  }
}
