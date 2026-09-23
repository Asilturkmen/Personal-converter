import { AudioIcon, VideoIcon } from './Icons';
import type { Mode } from '../types';

interface Props {
  mode: Mode;
  onChange: (mode: Mode) => void;
  videoAvailable: boolean;
  audioAvailable: boolean;
  disabled?: boolean;
}

const tabBase =
  'flex h-11 grow items-center justify-center gap-2.5 rounded-control text-[15px] font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-50';

export default function FormatTabs({ mode, onChange, videoAvailable, audioAvailable, disabled = false }: Props) {
  return (
    <div role="tablist" aria-label="Çıktı biçimi" className="flex gap-1 rounded-[16px] border border-line-soft bg-surface-2 p-1">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'video'}
        disabled={disabled || !videoAvailable}
        onClick={() => onChange('video')}
        className={tabBase + (mode === 'video' ? ' bg-surface text-ink shadow-tab' : ' text-muted')}
      >
        <VideoIcon />
        Video · MP4
      </button>

      <button
        type="button"
        role="tab"
        aria-selected={mode === 'audio'}
        disabled={disabled || !audioAvailable}
        onClick={() => onChange('audio')}
        className={tabBase + (mode === 'audio' ? ' bg-surface text-ink shadow-tab' : ' text-muted')}
      >
        <AudioIcon />
        Ses · MP3
      </button>
    </div>
  );
}
