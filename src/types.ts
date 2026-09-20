export type Platform = 'youtube' | 'instagram' | 'other';

export type Mode = 'video' | 'audio';

/** Tek bir indirilebilir varyant: 1080p MP4 ya da 320 kbps MP3. */
export interface QualityOption {
  id: string;
  label: string;
  /** Satırın altındaki açıklama: "Full HD · 60 fps" gibi. */
  sub: string;
  /** Tahmini dosya boyutu. Bilinmiyorsa null. */
  sizeBytes: number | null;
  ext: 'mp4' | 'mp3';
}

/** Bir bağlantıyı çözdükten sonra arka ucun döndüğü bilgi. */
export interface MediaInfo {
  id: string;
  platform: Platform;
  title: string;
  author: string;
  durationSeconds: number;
  /** Kapak görselinin adresi. Yoksa arayüz yer tutucu gösterir. */
  thumbnailUrl: string | null;
  thumbnailWidth: number | null;
  thumbnailHeight: number | null;
  sourceLabel: string;
  hasSubtitles: boolean;
  video: QualityOption[];
  audio: QualityOption[];
}

export interface DownloadRequest {
  url: string;
  mode: Mode;
  qualityId: string;
  subtitles: boolean;
  cover: boolean;
}

export interface DownloadTicket {
  /** Tarayıcının açacağı dosya adresi. */
  downloadUrl: string;
  filename: string;
}
