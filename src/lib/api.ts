import type { AudioOptions, MediaFormat, MediaInfo } from '../types';
import { safeFilename } from './format';

/*
  Backend ile konuşan tek dosya. Yollar geliştirmede Vite proxy'si
  (vite.config.ts), sunucuda aynı origin üzerinden gider; CORS yok.
*/

/** Blob'a toplanabilecek en büyük dosya. Üstü telefonda belleği patlatır. */
const BLOB_LIMIT = 250 * 1024 * 1024;

const NETWORK_ERROR = 'Sunucuya ulaşılamadı. Bağlantını kontrol edip tekrar dene.';
const STREAM_BROKEN = 'İndirme yarıda kesildi, dosya eksik kaldı. Tekrar dene.';

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    /* JSON değilse genel mesaja düş */
  }
  if (response.status === 502 || response.status === 504) return 'Sunucu şu an yanıt vermiyor. Birkaç saniye sonra tekrar dene.';
  return 'Beklenmeyen bir hata oluştu. Tekrar dene.';
}

export async function fetchMediaInfo(url: string): Promise<MediaInfo> {
  let response: Response;
  try {
    response = await fetch('/api/info?url=' + encodeURIComponent(url));
  } catch {
    throw new Error(NETWORK_ERROR);
  }
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

export function downloadHref(info: MediaInfo, format: MediaFormat, options: AudioOptions): string {
  const params = new URLSearchParams({ url: info.url, format: format.id });
  if (format.kind === 'audio') {
    if (options.cover) params.set('cover', '1');
    if (options.tags) params.set('tags', '1');
  }
  return '/api/download?' + params.toString();
}

export type DownloadResult = 'saved' | 'handed-off' | 'cancelled';

interface DownloadArgs {
  info: MediaInfo;
  format: MediaFormat;
  options: AudioOptions;
  signal: AbortSignal;
  /** Akış başladığında ve her parçada çağrılır. */
  onProgress: (received: number, estimated: number) => void;
}

/*
  Üç katmanlı indirme, sırayla:

  1. showSaveFilePicker varsa: konum sorulur, akış doğrudan diske yazılır.
     RAM'de birikme yok, ilerleme gösterilir.
  2. Yoksa ve dosya < 250 MB ise: akış okunur, ilerleme gösterilir, parçalar
     Blob'da toplanıp kaydedilir. Brave bu API'yi varsayılan olarak kapatıyor,
     Firefox ve Safari'de hiç yok — kullanıcıların çoğu buraya düşer.
  3. Diğer durumlarda: tarayıcının kendi indiricisine devredilir.

  ÖNEMLİ: Bu fonksiyon tıklama işleyicisinden doğrudan, arada hiçbir await
  olmadan çağrılmalı. showSaveFilePicker aşağıda ilk await'ten önce çağrılıyor;
  önce fetch beklenirse tarayıcı "user activation" süresini aşar ve picker açılmaz.
*/
export async function startDownload({ info, format, options, signal, onProgress }: DownloadArgs): Promise<DownloadResult> {
  const href = downloadHref(info, format, options);
  const ext = format.kind === 'audio' ? 'mp3' : 'mp4';
  const filename = safeFilename(info.title, ext);

  // --- 1. katman ------------------------------------------------------------
  if (typeof window.showSaveFilePicker === 'function') {
    // await'ten önce: user activation henüz geçerli.
    const picking = window.showSaveFilePicker({
      suggestedName: filename,
      startIn: 'downloads',
      types: [
        ext === 'mp3'
          ? { description: 'MP3 ses', accept: { 'audio/mpeg': ['.mp3'] } }
          : { description: 'MP4 video', accept: { 'video/mp4': ['.mp4'] } },
      ],
    });

    let handle: FileSystemFileHandle;
    try {
      handle = await picking;
    } catch (error) {
      // Kullanıcı iptal etti: sessizce çık.
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled';
      throw error;
    }

    const response = await request(href, signal);
    const writable = await handle.createWritable();
    try {
      await pump(response, format, signal, onProgress, (chunk) => writable.write(chunk));
      await writable.close();
    } catch (error) {
      await writable.abort().catch(() => undefined);
      throw error;
    }
    return 'saved';
  }

  // --- 2. katman ------------------------------------------------------------
  if (format.estimatedBytes < BLOB_LIMIT) {
    const response = await request(href, signal);
    const parts: BlobPart[] = [];
    await pump(response, format, signal, onProgress, (chunk) => {
      parts.push(chunk);
    });

    const blob = new Blob(parts, { type: ext === 'mp3' ? 'audio/mpeg' : 'video/mp4' });
    const objectUrl = URL.createObjectURL(blob);
    clickLink(objectUrl, filename);
    // Tıklamadan hemen sonra iptal edilirse bazı tarayıcılar indirmeyi başlatmıyor.
    setTimeout(() => URL.revokeObjectURL(objectUrl), 10_000);
    return 'saved';
  }

  // --- 3. katman ------------------------------------------------------------
  // Büyük dosya ve API yok: tarayıcının kendi göstergesi kullanılsın.
  clickLink(href, filename);
  return 'handed-off';
}

async function request(href: string, signal: AbortSignal): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(href, { signal, cache: 'no-store' });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error(NETWORK_ERROR);
  }
  if (!response.ok || !response.body) throw new Error(await readError(response));
  return response;
}

/** Akışı okur, baytları sayar. Akış yarıda koparsa hata yükseltir. */
async function pump(
  response: Response,
  format: MediaFormat,
  signal: AbortSignal,
  onProgress: (received: number, estimated: number) => void,
  write: (chunk: Uint8Array<ArrayBuffer>) => unknown,
): Promise<void> {
  const header = Number(response.headers.get('X-Estimated-Bytes'));
  const estimated = header > 0 ? header : format.estimatedBytes;
  const reader = (response.body as ReadableStream<Uint8Array<ArrayBuffer>>).getReader();
  let received = 0;
  onProgress(0, estimated);

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      await write(value);
      received += value.byteLength;
      onProgress(received, estimated);
    }
  } catch (error) {
    if (signal.aborted) throw error;
    // Sunucu 200 döndükten sonra akışı kesti (ffmpeg hatası, limit aşımı):
    // yarım dosya başarılı sayılmaz.
    throw new Error(STREAM_BROKEN);
  }

  if (received === 0) throw new Error(STREAM_BROKEN);
}

function clickLink(href: string, filename: string) {
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  link.rel = 'noopener';
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  link.remove();
}
