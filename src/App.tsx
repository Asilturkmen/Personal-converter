import { useMemo, useRef, useState } from 'react';
import Header from './components/Header';
import UrlInput from './components/UrlInput';
import EmptyState from './components/EmptyState';
import LoadingState from './components/LoadingState';
import FetchError from './components/FetchError';
import SourceCards from './components/SourceCards';
import MediaPreview from './components/MediaPreview';
import FormatTabs from './components/FormatTabs';
import QualityList from './components/QualityList';
import OptionToggles from './components/OptionToggles';
import DownloadButton from './components/DownloadButton';
import DownloadStatus from './components/DownloadStatus';
import Footer from './components/Footer';
import { fetchMediaInfo, startDownload } from './lib/api';
import { useTheme } from './hooks/useTheme';
import type { AudioOptions, DownloadState, MediaFormat, MediaInfo, Mode } from './types';

/** Varsayılan: 720p varsa o, yoksa en yüksek video. */
function defaultVideo(formats: MediaFormat[]): string | null {
  const videos = formats.filter((format) => format.kind === 'video');
  return (videos.find((format) => format.height === 720) ?? videos[videos.length - 1])?.id ?? null;
}

export default function App() {
  const { theme, toggle } = useTheme();

  const [url, setUrl] = useState('');
  const [info, setInfo] = useState<MediaInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const lastRequest = useRef(0);
  const [inputKey, setInputKey] = useState(0);

  const [mode, setMode] = useState<Mode>('video');
  const [videoId, setVideoId] = useState<string | null>(null);
  const [audioOptions, setAudioOptions] = useState<AudioOptions>({ cover: true, tags: true });

  const [download, setDownload] = useState<DownloadState>({ phase: 'idle' });
  const abortRef = useRef<AbortController | null>(null);
  const downloading = download.phase === 'starting' || download.phase === 'streaming';

  const videos = useMemo(() => info?.formats.filter((format) => format.kind === 'video') ?? [], [info]);
  const audio = useMemo(() => info?.formats.filter((format) => format.kind === 'audio') ?? [], [info]);
  const options = mode === 'video' ? videos : audio;
  const selected = mode === 'video' ? (videos.find((format) => format.id === videoId) ?? null) : (audio[0] ?? null);

  async function handleFetch(target: string) {
    const value = target.trim();
    if (!value) return;

    const requestId = ++lastRequest.current;
    abortRef.current?.abort();
    setLoading(true);
    setFetchError(null);
    setInfo(null);
    setDownload({ phase: 'idle' });

    try {
      const result = await fetchMediaInfo(value);
      if (requestId !== lastRequest.current) return; // bu arada yeni bir bağlantı geldi
      const firstVideo = defaultVideo(result.formats);
      setInfo(result);
      setVideoId(firstVideo);
      setMode(firstVideo ? 'video' : 'audio');
    } catch (caught) {
      if (requestId !== lastRequest.current) return;
      setFetchError(caught instanceof Error ? caught.message : 'Beklenmeyen bir hata oluştu. Tekrar dene.');
    } finally {
      if (requestId === lastRequest.current) setLoading(false);
    }
  }

  function handleModeChange(next: Mode) {
    setMode(next);
    if (!downloading) setDownload({ phase: 'idle' });
  }

  // Tıklama işleyicisi: startDownload'dan önce hiçbir await olmamalı
  // (showSaveFilePicker kullanıcı etkileşimi süresi içinde açılmak zorunda).
  function handleDownload() {
    if (!info || !selected || downloading) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setDownload({ phase: 'starting' });

    startDownload({
      info,
      format: selected,
      options: audioOptions,
      signal: controller.signal,
      onProgress: (received, estimated) => setDownload({ phase: 'streaming', received, estimated }),
    })
      .then((result) => {
        if (result === 'cancelled') {
          setDownload({ phase: 'idle' });
        } else if (result === 'handed-off') {
          setDownload({ phase: 'handed-off' });
        } else {
          setDownload((current) => ({ phase: 'done', received: current.phase === 'streaming' ? current.received : 0 }));
          // Yeni bağlantıya hazır: kutuyu seç, yapıştırınca eskisinin yerine geçsin.
          const input = document.getElementById('media-url') as HTMLInputElement | null;
          input?.focus();
          input?.select();
        }
      })
      .catch((caught) => {
        if (controller.signal.aborted) {
          setDownload({ phase: 'idle' });
          return;
        }
        setDownload({
          phase: 'error',
          message: caught instanceof Error ? caught.message : 'İndirme başarısız oldu. Tekrar dene.',
        });
      })
      .finally(() => {
        if (abortRef.current === controller) abortRef.current = null;
      });
  }

  function handleCancel() {
    abortRef.current?.abort();
  }

  // Sayfayı ilk açılış hâline döndürür. İndirme sürerken çağrılmaz (buton pasif).
  function handleClear() {
    if (downloading) return;
    lastRequest.current += 1; // yolda olan bir getirme varsa sonucu yok sayılsın
    setUrl('');
    setInfo(null);
    setLoading(false);
    setFetchError(null);
    setMode('video');
    setVideoId(null);
    setAudioOptions({ cover: true, tags: true });
    setDownload({ phase: 'idle' });
    // UrlInput yeniden kurulur: "pano izni verilmedi" uyarısı da temizlenir.
    setInputKey((key) => key + 1);
    requestAnimationFrame(() => document.getElementById('media-url')?.focus());
  }

  const canClear = url.trim() !== '' || info !== null || fetchError !== null || loading;

  const downloadLabel = selected ? selected.label + ' indir' : 'İndir';

  return (
    <div className="flex min-h-dvh flex-col">
      <Header theme={theme} onToggleTheme={toggle} />

      <main className="mx-auto w-full max-w-[1120px] grow px-5 pt-v32 md:px-10 md:pt-v40">
        <h1 className="text-[length:var(--t-title)] font-extrabold leading-[1.1] tracking-[-0.03em]">
          Bağlantıyı yapıştır.
        </h1>
        <p className="mt-v12 max-w-[640px] text-[15px] font-medium leading-relaxed text-muted md:text-base">
          YouTube ve Instagram videolarını 1080p'ye kadar indir ya da MP3'e çevir.
        </p>

        <div className="mt-v24">
          <UrlInput
            key={inputKey}
            value={url}
            onChange={setUrl}
            onSubmit={handleFetch}
            loading={loading}
            onClear={canClear ? handleClear : undefined}
            clearDisabled={downloading}
          />
        </div>

        {loading ? (
          <LoadingState />
        ) : fetchError ? (
          <FetchError message={fetchError} onRetry={() => handleFetch(url)} />
        ) : info ? (
          <div className="mt-v32 grid grid-cols-1 gap-v32 md:grid-cols-[var(--w-preview)_1fr] md:gap-v40">
            <MediaPreview info={info} />

            <div className="min-w-0">
              <FormatTabs
                mode={mode}
                onChange={handleModeChange}
                videoAvailable={videos.length > 0}
                audioAvailable={audio.length > 0}
                disabled={downloading}
              />

              <QualityList
                formats={options}
                selectedId={selected?.id ?? null}
                onSelect={setVideoId}
                legend={mode === 'video' ? 'Çözünürlük' : 'Ses'}
                disabled={downloading}
              />

              {mode === 'audio' && <OptionToggles options={audioOptions} onChange={setAudioOptions} disabled={downloading} />}

              <DownloadButton label={downloadLabel} busy={downloading} disabled={!selected} onClick={handleDownload} />
              <DownloadStatus state={download} onRetry={handleDownload} onCancel={handleCancel} />
            </div>
          </div>
        ) : (
          <>
            <EmptyState />
            <SourceCards />
          </>
        )}
      </main>

      {/*
        Footer main'in dışında duruyor. main `grow` olduğu için artan boşluk
        main'e gider ve footer sayfanın dibine yapışır — boşluk footer'ın
        altında değil üstünde kalır. İçerik uzunsa normal akışına döner.
      */}
      <div className="mx-auto w-full max-w-[1120px] px-5 md:px-10">
        <Footer />
      </div>
    </div>
  );
}
