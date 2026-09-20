import { AudioIcon, VideoIcon } from './Icons';
import type { Mode } from '../types';

interface Props {
  mode: Mode;
  onChange: (mode: Mode) => void;
}

const tabBase =
  'flex h-11 grow items-center justify-center gap-2.5 rounded-control text-[15px] font-bold transition-colors';

export default function FormatTabs({ mode, onChange }: Props) {
  return (
    <div role="tablist" aria-label="Çıktı biçimi" className="flex gap-1 rounded-[16px] border border-line-soft bg-surface-2 p-1">
      <button
        type="button"
        role="tab"
        aria-selected={mode === 'video'}
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
        onClick={() => onChange('audio')}
        className={tabBase + (mode === 'audio' ? ' bg-surface text-ink shadow-tab' : ' text-muted')}
      >
        <AudioIcon />
        Ses · MP3
      </button>
    </div>
  );
}
