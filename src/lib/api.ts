import type { AudioOptions, MediaFormat, MediaInfo } from '../types';
import { safeFilename } from './format';

/*
  Backend ile konuşan tek dosya. Yollar geliştirmede Vite proxy'si
  (vite.config.ts), sunucuda aynı origin üzerinden gider; CORS yok.
*/

const MB = 1024 * 1024;

const NETWORK_ERROR = 'Sunucuya ulaşılamadı. Bağlantını kontrol edip tekrar dene.';
const STREAM_BROKEN = 'İndirme yarıda kesildi, dosya eksik kaldı. Tekrar dene.';
const SAVE_FAILED = 'Dosya kaydedilemedi. Diskte yer olduğundan emin olup tekrar dene.';

async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === 'string') return body.detail;
  } catch {
    /* JSON değilse genel mesaja düş */
  }
  // Backend'in kendi hataları her zaman JSON'dur. JSON olmayan bir 5xx'i önündeki
  // proxy üretmiştir (geliştirmede Vite boş bir 500, sunucuda nginx 502 döner):
  // backend kapalı ya da ulaşılamıyor.
  if (response.status >= 500) return NETWORK_ERROR;
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

/**
 * Blob'a (RAM'e) toplanabilecek en büyük dosya. Bu sınırın üstü tarayıcının
 * kendi indiricisine devredilir. Android Chrome'da showSaveFilePicker yok;
 * düşük bellekli telefonda 250 MB'lık Blob sekmeyi çökertebilir. deviceMemory
 * (GB, Chromium) varsa ona göre, yoksa dokunmatik cihazlarda daha temkinli.
 */
export function blobLimit(): number {
  const memory = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  if (memory) return Math.min(250, Math.max(64, memory * 32)) * MB; // 2 GB → 64, 4 GB → 128, 8 GB → 250
  const coarse = window.matchMedia?.('(pointer: coarse)').matches;
  return (coarse ? 100 : 250) * MB;
}

interface Ticket {
  ticket: string;
  filename: string;
  estimatedBytes: number;
}

/**
 * Sunucuda yer ayırır ve ffmpeg'i başlatır. Yoğunluk, IP sınırı, boyut ya da
 * kaynağa erişilememe gibi her hata burada, dosya indirmesi başlamadan döner.
 */
async function prepare(info: MediaInfo, format: MediaFormat, options: AudioOptions, signal: AbortSignal): Promise<Ticket> {
  const audio = format.kind === 'audio';
  let response: Response;
  try {
    response = await fetch('/api/download/prepare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: info.url, format: format.id, cover: audio && options.cover, tags: audio && options.tags }),
      signal,
    });
  } catch (error) {
    if (signal.aborted) throw error;
    throw new Error(NETWORK_ERROR);
  }
  if (!response.ok) throw new Error(await readError(response));
  return response.json();
}

/** Kullanılmayacak bileti bırakır; sunucu TTL'i beklemeden yeri boşaltır. */
function release(ticket: Ticket) {
  fetch('/api/download/' + encodeURIComponent(ticket.ticket), { method: 'DELETE', keepalive: true }).catch(() => undefined);
}

const ticketHref = (ticket: Ticket) => '/api/download?ticket=' + encodeURIComponent(ticket.ticket);

export type DownloadResult = 'saved' | 'handed-off' | 'cancelled';

interface DownloadArgs {
  info: MediaInfo;
  format: MediaFormat;
  options: AudioOptions;
  signal: AbortSignal;
  /** Akış başladığında ve her parçada çağrılır. */
  onProgress: (received: number, estimated: number, exact: boolean) => void;
}

/*
  Üç katmanlı indirme, sırayla. Üçü de önce prepare ile yer ayırtır; böylece
  her hata dosya indirilmeye başlamadan arayüzde gösterilir.

  1. showSaveFilePicker varsa: konum sorulur, akış doğrudan diske yazılır.
     RAM'de birikme yok, ilerleme gösterilir. Pencere açılamazsa (iframe,
     kurumsal politika) sonraki katmanlara geçilir.
  2. Yoksa ve dosya blobLimit()'ten küçükse: akış okunur, ilerleme gösterilir,
     parçalar Blob'da toplanıp kaydedilir. Brave bu API'yi varsayılan olarak
     kapatıyor, Firefox ve Safari'de hiç yok — kullanıcıların çoğu buraya düşer.
  3. Diğer durumlarda: tarayıcının kendi indiricisine devredilir.

  ÖNEMLİ: Bu fonksiyon tıklama işleyicisinden doğrudan, arada hiçbir await
  olmadan çağrılmalı. showSaveFilePicker aşağıda ilk await'ten önce çağrılıyor;
  önce fetch beklenirse tarayıcı "user activation" süresini aşar ve picker açılmaz.
*/
export async function startDownload({ info, format, options, signal, onProgress }: DownloadArgs): Promise<DownloadResult> {
  const ext = format.kind === 'audio' ? 'mp3' : 'mp4';
  const filename = safeFilename(info.title, ext);

  // Yer ayırtır ve akışı açar. Sunucu bileti GET geldiği anda tüketir. GET
  // sunucuya hiç ulaşmadıysa (ağ koptu, iptal) bilet TTL dolana kadar yer
  // tutar; kullanıcı "Tekrar dene"ye basınca "zaten indirmen var" görürdü.
  // Bu yüzden bırakılır; ulaştıysa bilet zaten tüketilmiştir, istek bir şey yapmaz.
  const open = async () => {
    const ticket = await prepare(info, format, options, signal);
    try {
      return await request(ticketHref(ticket), signal);
    } catch (error) {
      release(ticket);
      throw error;
    }
  };

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

    let handle: FileSystemFileHandle | null = null;
    try {
      handle = await picking;
    } catch (error) {
      // Kullanıcı iptal etti: sessizce çık.
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled';
      // Pencere hiç açılamadı (iframe, kurumsal politika): aşağıdaki katmanlar
      // kullanıcı etkileşimi gerektirmez, indirme onlarla sürer.
    }

    if (handle) {
      // Picker yeni bir adı seçildiği anda boş bir dosya olarak oluşturur.
      // Bundan sonraki her hata ya da iptal, geride bu boş dosyayı bırakmamalı.
      // Kullanıcı var olan bir dosyanın üzerine yazmayı seçtiyse ona dokunulmaz:
      // createWritable geçici bir kopyaya yazar, abort() eski içeriği korur.
      const created = await isEmpty(handle);
      try {
        // Dosya sunucuda yer ayrılmadan açılır: yazılamıyorsa yer hiç tutulmaz.
        const writable = await handle.createWritable().catch(() => {
          throw new Error(SAVE_FAILED);
        });
        try {
          const response = await open();
          await pump(response, format, signal, onProgress, (chunk) => writable.write(chunk));
          // Yazılanlar dosyaya ancak close() ile geçer; disk doluysa burada anlaşılır.
          await writable.close().catch(() => {
            throw new Error(SAVE_FAILED);
          });
        } catch (error) {
          await writable.abort().catch(() => undefined);
          throw error;
        }
      } catch (error) {
        if (created) await removeFile(handle);
        throw error;
      }
      return 'saved';
    }
  }

  // --- 2. katman ------------------------------------------------------------
  if (format.estimatedBytes < blobLimit()) {
    const response = await open();
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
  // Büyük dosya ve API yok: tarayıcının kendi göstergesi kullanılsın. Yer
  // önce ayrıldığı için yoğunluk/sınır hataları buraya gelmeden gösterilir.
  const ticket = await prepare(info, format, options, signal);
  clickLink(ticketHref(ticket), ticket.filename);
  return 'handed-off';
}

/** Boş dosya = picker'ın az önce oluşturduğu. Okunamazsa silinmez (güvenli taraf). */
async function isEmpty(handle: FileSystemFileHandle): Promise<boolean> {
  try {
    return (await handle.getFile()).size === 0;
  } catch {
    return false;
  }
}

async function removeFile(handle: FileSystemFileHandle) {
  // FileSystemHandle.remove(): Chromium 110+. Yoksa boş dosya kalır; akış
  // hatası zaten kullanıcıya gösteriliyor.
  const removable = handle as FileSystemFileHandle & { remove?: () => Promise<void> };
  await removable.remove?.().catch(() => undefined);
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

/** Akışı okur, baytları sayar. Akış yarıda koparsa ya da yazılamazsa hata yükseltir. */
async function pump(
  response: Response,
  format: MediaFormat,
  signal: AbortSignal,
  onProgress: (received: number, estimated: number, exact: boolean) => void,
  write: (chunk: Uint8Array<ArrayBuffer>) => unknown,
): Promise<void> {
  const header = Number(response.headers.get('X-Estimated-Bytes'));
  const estimated = header > 0 ? header : format.estimatedBytes;
  const exact = format.estimateExact && estimated > 0;
  const reader = (response.body as ReadableStream<Uint8Array<ArrayBuffer>>).getReader();
  let received = 0;
  onProgress(0, estimated, exact);

  try {
    for (;;) {
      let chunk: ReadableStreamReadResult<Uint8Array<ArrayBuffer>>;
      try {
        chunk = await reader.read();
      } catch (error) {
        if (signal.aborted) throw error;
        // Sunucu 200 döndükten sonra akışı kesti (kaynak koptu, limit aşıldı):
        // yarım dosya başarılı sayılmaz.
        throw new Error(STREAM_BROKEN);
      }
      if (chunk.done) break;
      try {
        await write(chunk.value);
      } catch {
        throw new Error(SAVE_FAILED); // disk dolu, izin yok
      }
      received += chunk.value.byteLength;
      onProgress(received, estimated, exact);
    }
  } catch (error) {
    // Okuma bırakılırsa bağlantı açık kalır ve sunucu indirme yerini tutmaya
    // devam eder; kullanıcı yeniden denediğinde "zaten indirmen var" görürdü.
    reader.cancel().catch(() => undefined);
    throw error;
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
