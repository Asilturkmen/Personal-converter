import { AlertIcon, CheckIcon, RetryIcon } from './Icons';
import { formatBytes, formatProgress } from '../lib/format';
import type { DownloadState } from '../types';

interface Props {
  state: DownloadState;
  onRetry: () => void;
  onCancel: () => void;
}

/*
  Yüzde tahmini boyuttan hesaplanır ve tahmin tutmayabilir: akış bitene
  kadar %99'da sabitlenir, bitince %100'e atlar. Gerçek bayt tahmini aşarsa
  çubuk geri sarmaz — sadece %99'da bekler.
*/
function percentOf(received: number, estimated: number): number {
  if (estimated <= 0) return 0;
  return Math.min(99, Math.floor((received / estimated) * 100));
}

const panel = 'mt-v14 rounded-control border border-line bg-surface px-4 py-3';

export default function DownloadStatus({ state, onRetry, onCancel }: Props) {
  if (state.phase === 'idle') return null;

  if (state.phase === 'starting' || state.phase === 'streaming') {
    const received = state.phase === 'streaming' ? state.received : 0;
    const estimated = state.phase === 'streaming' ? state.estimated : 0;
    const percent = percentOf(received, estimated);

    return (
      <div className={panel} role="status" aria-live="polite">
        {/* Tek satır + çubuk: panel 925 px ekranda sayfayı taşırmasın. */}
        <div className="flex items-baseline justify-between gap-3">
          <span className="text-sm font-bold">
            {state.phase === 'starting' ? 'Hazırlanıyor…' : 'İndiriliyor · %' + percent}
          </span>
          <span className="flex items-baseline gap-3 text-[13px] font-medium text-muted">
            <span className="truncate">
              {state.phase === 'starting' ? 'kaynak açılıyor' : formatProgress(received, Math.max(estimated, received))}
            </span>
            <button type="button" onClick={onCancel} className="shrink-0 font-semibold underline-offset-4 hover:text-ink hover:underline">
              İptal et
            </button>
          </span>
        </div>

        <div
          className="mt-2.5 h-2 overflow-hidden rounded-full bg-surface-2"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <div
            className={'h-full rounded-full bg-accent transition-[width] duration-300 ' + (state.phase === 'starting' ? 'w-1/4 animate-pulse' : '')}
            style={state.phase === 'streaming' ? { width: percent + '%' } : undefined}
          />
        </div>
      </div>
    );
  }

  if (state.phase === 'done') {
    return (
      <div className={panel + ' flex items-center gap-3'} role="status">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-pick text-accent">
          <CheckIcon className="h-4 w-4" />
        </span>
        <span className="flex flex-col">
          <span className="text-sm font-bold">İndirildi · {formatBytes(state.received)}</span>
          <span className="text-[13px] font-medium text-muted">Yeni bir bağlantı yapıştırabilirsin.</span>
        </span>
      </div>
    );
  }

  if (state.phase === 'handed-off') {
    return (
      <div className={panel + ' flex items-center gap-3'} role="status">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-pick text-accent">
          <CheckIcon className="h-4 w-4" />
        </span>
        <span className="flex flex-col">
          <span className="text-sm font-bold">İndirme tarayıcıya devredildi</span>
          <span className="text-[13px] font-medium text-muted">İlerlemeyi tarayıcının indirilenler listesinden takip et.</span>
        </span>
      </div>
    );
  }

  return (
    <div className={panel + ' flex flex-col gap-3 sm:flex-row sm:items-center'} role="alert">
      <span className="flex min-w-0 grow items-start gap-3">
        <AlertIcon className="mt-px h-[18px] w-[18px] text-muted" />
        <span className="text-sm font-semibold leading-relaxed">{state.message}</span>
      </span>
      <button
        type="button"
        onClick={onRetry}
        className="flex h-10 shrink-0 items-center justify-center gap-2 rounded-[11px] bg-chip px-4 text-sm font-semibold text-ink transition-colors hover:brightness-95"
      >
        <RetryIcon />
        Tekrar dene
      </button>
    </div>
  );
}
