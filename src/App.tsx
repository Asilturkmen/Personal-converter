import { useMemo, useState } from 'react';
import Header from './components/Header';
import UrlInput from './components/UrlInput';
import ErrorNote from './components/ErrorNote';
import EmptyState from './components/EmptyState';
import SourceCards from './components/SourceCards';
import MediaPreview from './components/MediaPreview';
import FormatTabs from './components/FormatTabs';
import QualityList from './components/QualityList';
import OptionToggles from './components/OptionToggles';
import DownloadButton from './components/DownloadButton';
import Footer from './components/Footer';
import { fetchMediaInfo, requestDownload } from './lib/api';
import { formatBytes } from './lib/format';
import { useTheme } from './hooks/useTheme';
import type { MediaInfo, Mode } from './types';

export default function App() {
  const { theme, toggle } = useTheme();

  const [url, setUrl] = useState('');
  const [info, setInfo] = useState<MediaInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>('video');
  const [qualityId, setQualityId] = useState<string | null>(null);
  const [subtitles, setSubtitles] = useState(true);
  const [cover, setCover] = useState(false);

  const options = useMemo(() => {
    if (!info) return [];
    return mode === 'video' ? info.video : info.audio;
  }, [info, mode]);

  const selected = options.find((option) => option.id === qualityId) ?? options[0] ?? null;

  async function handleFetch() {
    setLoading(true);
    setError(null);

    try {
      const result = await fetchMediaInfo(url.trim());
      setInfo(result);
      setMode('video');
      setQualityId(result.video[0]?.id ?? null);
      setSubtitles(result.hasSubtitles);
    } catch (caught) {
      setInfo(null);
      setError(caught instanceof Error ? caught.message : 'Beklenmeyen bir hata oluştu.');
    } finally {
      setLoading(false);
    }
  }

  function handleModeChange(next: Mode) {
    setMode(next);
    const list = info ? (next === 'video' ? info.video : info.audio) : [];
    setQualityId(list[0]?.id ?? null);
  }

  async function handleDownload() {
    if (!info || !selected) return;

    setBusy(true);
    setError(null);

    try {
      const ticket = await requestDownload({
        url: url.trim(),
        mode,
        qualityId: selected.id,
        subtitles,
        cover,
      });

      // Gerçek arka uç bağlandığında bu satır dosyayı indirmeye başlatır.
      if (ticket.downloadUrl !== '#') {
        window.location.assign(ticket.downloadUrl);
      } else {
        setError('Sahte veri modundasın: ' + ticket.filename + ' hazır olurdu.');
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'İndirme başlatılamadı.');
    } finally {
      setBusy(false);
    }
  }

  const downloadLabel = selected
    ? (mode === 'video' ? 'MP4 indir · ' : 'MP3 indir · ') +
      selected.label +
      ' · ' +
      formatBytes(selected.sizeBytes)
    : 'İndir';

  return (
    <div className="flex min-h-dvh flex-col">
      <Header theme={theme} onToggleTheme={toggle} />

      <main className="mx-auto w-full max-w-[1120px] grow px-5 pt-8 md:px-10 md:pt-11">
        <h1 className="text-[30px] font-extrabold leading-[1.1] tracking-[-0.03em] md:text-[40px]">
          Bağlantıyı yapıştır.
        </h1>
        <p className="mt-3 max-w-[640px] text-[15px] font-medium leading-relaxed text-muted md:text-base">
          YouTube ve Instagram videolarını dilediğin kalitede indir ya da doğrudan MP3'e çevir.
        </p>

        <div className="mt-6">
          <UrlInput value={url} onChange={setUrl} onSubmit={handleFetch} loading={loading} />
        </div>

        {error && <ErrorNote message={error} />}

        {info ? (
          <div className="mt-8 grid grid-cols-1 gap-8 md:grid-cols-[440px_1fr] md:gap-10">
            <MediaPreview info={info} />

            <div className="min-w-0">
              <FormatTabs mode={mode} onChange={handleModeChange} />

              <QualityList
                options={options}
                selectedId={selected?.id ?? null}
                onSelect={setQualityId}
                legend={mode === 'video' ? 'Çözünürlük' : 'Ses kalitesi'}
              />

              <OptionToggles
                mode={mode}
                subtitles={subtitles}
                cover={cover}
                subtitlesAvailable={info.hasSubtitles}
                onSubtitlesChange={setSubtitles}
                onCoverChange={setCover}
              />

              <DownloadButton label={downloadLabel} busy={busy} disabled={!selected} onClick={handleDownload} />
            </div>
          </div>
        ) : (
          <>
            <EmptyState />
            <SourceCards />
          </>
        )}

        <Footer />
      </main>
    </div>
  );
}
