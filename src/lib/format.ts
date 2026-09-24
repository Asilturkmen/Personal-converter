const UNITS = ['KB', 'MB', 'GB'];

function scale(bytes: number): { value: number; unit: number } {
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return { value, unit };
}

function round(value: number): string {
  const rounded = value >= 100 ? Math.round(value) : Math.round(value * 10) / 10;
  return rounded.toLocaleString('tr-TR');
}

/** 1536000 -> "1,5 MB" */
export function formatBytes(bytes: number | null): string {
  if (bytes === null) return '-';
  if (bytes < 1024) return bytes + ' B';
  const { value, unit } = scale(bytes);
  return round(value) + ' ' + UNITS[unit];
}

/** Tahmini boyut: "~118 MB". Bilinmiyorsa boş. */
export function formatEstimate(bytes: number): string {
  return bytes > 0 ? '~' + formatBytes(bytes) : '';
}

/** İlerleme metni, iki sayı da toplamın biriminde: "45 / 118 MB". */
export function formatProgress(received: number, total: number): string {
  const { unit } = scale(Math.max(total, received, 1024));
  const divisor = 1024 ** (unit + 1);
  return round(received / divisor) + ' / ' + round(total / divisor) + ' ' + UNITS[unit];
}

/** 754 -> "12:34" */
export function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = Math.floor(totalSeconds % 60);
  const pad = (n: number) => String(n).padStart(2, '0');

  return hours > 0 ? hours + ':' + pad(minutes) + ':' + pad(seconds) : minutes + ':' + pad(seconds);
}

export function platformLabel(platform: string): string {
  if (platform === 'youtube') return 'YouTube';
  if (platform === 'instagram') return 'Instagram';
  return 'Bağlantı';
}

/** Kalite satırının alt metni: "Full HD · 60 fps · H.264". */
export function qualityNote(height: number | undefined, fps?: number | null, codec?: string | null): string {
  const name =
    !height ? null
    : height >= 2160 ? '4K'
    : height >= 1440 ? '2K'
    : height >= 1080 ? 'Full HD'
    : height >= 720 ? 'HD'
    : height >= 480 ? 'SD'
    : 'Veri dostu';
  return [name, fps && fps > 30 ? fps + ' fps' : null, codec].filter(Boolean).join(' · ');
}

/* Backend'deki names.py ile aynı kurallar: Windows'ta yasak karakterler ve
   yön denetim karakterleri temizlenir, Türkçe karakterler korunur. */
// eslint-disable-next-line no-control-regex
const FORBIDDEN = /[<>:"/\\|?*\u0000-\u001f\u007f\u200e\u200f\u202a-\u202e\u2066-\u2069]/g;
const RESERVED = /^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i;

export function safeFilename(title: string, ext: string): string {
  let name = (title || '').replace(FORBIDDEN, ' ').replace(/\s+/g, ' ').trim().replace(/^[ .]+|[ .]+$/g, '');
  name = name.slice(0, 150).replace(/[ .]+$/, '');
  if (!name) name = 'video';
  if (RESERVED.test(name.split('.')[0])) name = '_' + name;
  return name + '.' + ext;
}
