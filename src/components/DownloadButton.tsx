import { DownloadIcon, SpinnerIcon } from './Icons';

interface Props {
  label: string;
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
}

export default function DownloadButton({ label, busy, disabled, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || busy}
      className="mt-v24 flex h-[clamp(48px,4.31vh,56px)] w-full items-center justify-center gap-2.5 rounded-[16px] bg-accent text-base font-bold text-white transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50"
    >
      {busy ? <SpinnerIcon /> : <DownloadIcon />}
      {busy ? 'Hazırlanıyor…' : label}
    </button>
  );
}
