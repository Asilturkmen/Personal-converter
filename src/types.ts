export type Platform = 'youtube' | 'instagram';

export type Mode = 'video' | 'audio';

/** Backend'in hazırladığı tek bir indirilebilir seçenek: "v720" ya da "mp3". */
export interface MediaFormat {
  id: string;
  label: string;
  kind: Mode;
  /** İlerleme çubuğu için tahmini boyut (bayt). */
  estimatedBytes: number;
  /**
   * true: kaynağın bildirdiği dosya boyutundan (yüzde güvenilir).
   * false: bit hızı × süre tahmini; HLS'te genelde fazla çıkar.
   */
  estimateExact: boolean;
  /** Yalnızca video: kısa kenara göre çözünürlük (dikey 1080x1920 → 1080). */
  height?: number;
  fps?: number | null;
  codec?: string | null;
  /** Yalnızca MP3: sabit bit hızı (kbps). */
  bitrate?: number;
}

/** GET /api/info yanıtı. */
export interface MediaInfo {
  url: string;
  source: Platform;
  title: string;
  uploader: string;
  /** Saniye. Bilinmiyorsa 0. */
  duration: number;
  /** Aynı origin'deki kapak adresi (/api/thumbnail?...). Yoksa null. */
  thumbnail: string | null;
  /** Kaynak videonun en büyük karesi; dikey mi yatay mı buradan anlaşılır. */
  width: number | null;
  height: number | null;
  formats: MediaFormat[];
}

/** Yalnızca MP3 için anlamlı seçenekler. */
export interface AudioOptions {
  cover: boolean;
  tags: boolean;
}

export type DownloadState =
  | { phase: 'idle' }
  | { phase: 'starting' }
  | { phase: 'streaming'; received: number; estimated: number; exact: boolean }
  | { phase: 'done'; received: number }
  | { phase: 'handed-off' }
  | { phase: 'error'; message: string };
