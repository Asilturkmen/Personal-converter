import type { DownloadRequest, DownloadTicket, MediaInfo, Platform } from '../types';

/*
  ---------------------------------------------------------------------------
  SAHTE (MOCK) API
  ---------------------------------------------------------------------------
  Arayuzun tamami yalnizca bu iki fonksiyona bagli. Arka ucu yazdiginda
  govdelerini gercek fetch cagrilariyla degistirmen yeterli, baska hicbir
  dosyaya dokunmana gerek yok.

  Ornek gercek karsiliklari en altta yorum icinde duruyor.
*/

const MOCK_DELAY_MS = 700;

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function detectPlatform(url: string): Platform {
  const value = url.toLowerCase();
  if (value.includes('youtube.com') || value.includes('youtu.be')) return 'youtube';
  if (value.includes('instagram.com')) return 'instagram';
  return 'other';
}

export function isSupportedUrl(url: string): boolean {
  return detectPlatform(url) !== 'other';
}

export async function fetchMediaInfo(url: string): Promise<MediaInfo> {
  await delay(MOCK_DELAY_MS);

  const platform = detectPlatform(url);
  if (platform === 'other') {
    throw new Error('Bu bağlantıyı tanıyamadım. YouTube ya da Instagram bağlantısı yapıştır.');
  }

  const short = platform === 'instagram' || url.includes('/shorts/');

  return {
    id: 'mock-1',
    platform,
    title: short ? 'Kısa video başlığı burada görünür' : 'Video başlığı burada görünür',
    author: platform === 'instagram' ? '@hesapadi' : '@kanaladi',
    durationSeconds: short ? 58 : 754,
    thumbnailUrl: null,
    thumbnailWidth: 1280,
    thumbnailHeight: 720,
    sourceLabel: short ? '1080x1920 kaynak' : '1080p60 kaynak',
    hasSubtitles: platform === 'youtube',
    video: short
      ? [
          { id: '1080p', label: '1080p', sub: 'Full HD · MP4', sizeBytes: 25_165_824, ext: 'mp4' },
          { id: '720p', label: '720p', sub: 'HD · MP4', sizeBytes: 13_631_488, ext: 'mp4' },
          { id: '480p', label: '480p', sub: 'Veri dostu · MP4', sizeBytes: 7_340_032, ext: 'mp4' },
        ]
      : [
          { id: '2160p', label: '2160p', sub: '4K · MP4 (H.264 + AAC)', sizeBytes: 1_503_238_553, ext: 'mp4' },
          { id: '1440p', label: '1440p', sub: '2K · MP4 (H.264 + AAC)', sizeBytes: 754_974_720, ext: 'mp4' },
          { id: '1080p', label: '1080p', sub: 'Full HD · 60 fps', sizeBytes: 155_189_248, ext: 'mp4' },
          { id: '720p', label: '720p', sub: 'HD · 30 fps', sizeBytes: 77_594_624, ext: 'mp4' },
          { id: '480p', label: '480p', sub: 'Veri dostu', sizeBytes: 39_845_888, ext: 'mp4' },
        ],
    // MP3'te kalite seçimi yok: her zaman en yüksek kalite (320 kbps) iner.
    audio: [{ id: '320', label: '320 kbps', sub: 'MP3 · en yüksek kalite', sizeBytes: 29_360_128, ext: 'mp3' }],
  };
}

export async function requestDownload(request: DownloadRequest): Promise<DownloadTicket> {
  await delay(MOCK_DELAY_MS);

  const ext = request.mode === 'audio' ? 'mp3' : 'mp4';
  return {
    downloadUrl: '#',
    filename: 'indirilen-dosya-' + request.qualityId + '.' + ext,
  };
}

/*
  Gercek arka uc baglandiginda govdeler soyle olur:

  export async function fetchMediaInfo(url: string): Promise<MediaInfo> {
    const response = await fetch('/api/info?url=' + encodeURIComponent(url));
    if (!response.ok) throw new Error('Video bilgisi alınamadı.');
    return response.json();
  }

  export async function requestDownload(request: DownloadRequest): Promise<DownloadTicket> {
    const response = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    if (!response.ok) throw new Error('İndirme başlatılamadı.');
    return response.json();
  }
*/
