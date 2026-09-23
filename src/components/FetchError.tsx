import { AlertIcon, RetryIcon } from './Icons';

interface Props {
  message: string;
  onRetry: () => void;
}

/** Bağlantı çözülemediğinde boş durum kutusunun yerine geçer. */
export default function FetchError({ message, onRetry }: Props) {
  return (
    <div
      role="alert"
      className="mt-v32 flex min-h-[280px] flex-col items-center justify-center gap-v18 rounded-[22px] border border-dashed border-line bg-surface/60 px-6 py-[var(--p-empty)] md:min-h-[var(--h-empty)]"
    >
      <span className="flex h-[74px] w-[74px] items-center justify-center rounded-[22px] border border-line bg-surface text-muted">
        <AlertIcon className="h-[30px] w-[30px]" />
      </span>

      <div className="flex flex-col items-center gap-2">
        <span className="text-xl font-bold tracking-[-0.015em]">Bağlantı getirilemedi</span>
        <span className="max-w-[460px] text-center text-[15px] font-medium leading-relaxed text-muted">{message}</span>
      </div>

      <button
        type="button"
        onClick={onRetry}
        className="flex h-11 items-center justify-center gap-2 rounded-control border border-line bg-surface px-5 text-sm font-semibold text-ink transition-colors hover:bg-surface-2"
      >
        <RetryIcon />
        Tekrar dene
      </button>
    </div>
  );
}
