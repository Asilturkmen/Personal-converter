import { ImageIcon, PlayIcon } from './Icons';
import { formatDuration, platformLabel } from '../lib/format';
import type { MediaInfo } from '../types';

interface Props {
  info: MediaInfo;
}

export default function MediaPreview({ info }: Props) {
  return (
    <section>
      <div className="relative aspect-video w-full overflow-hidden rounded-card border border-line bg-thumb">
        {info.thumbnailUrl ? (
          <img src={info.thumbnailUrl} alt="" className="h-full w-full object-cover" />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2.5">
            <span className="flex h-[54px] w-[54px] items-center justify-center rounded-full bg-surface shadow-soft">
              <PlayIcon />
            </span>
            <span className="text-xs font-semibold tracking-[0.08em] text-thumb-ink">[ KAPAK GÖRSELİ ]</span>
          </div>
        )}

        <span className="absolute left-3.5 top-3.5 rounded-full bg-surface/90 px-2.5 py-1.5 text-xs font-bold text-ink backdrop-blur">
          {platformLabel(info.platform)}
        </span>
        <span className="absolute bottom-3.5 right-3.5 rounded-lg bg-black/75 px-2.5 py-1 text-xs font-bold text-white">
          {formatDuration(info.durationSeconds)}
        </span>
      </div>

      <h2 className="mt-v16 text-[19px] font-bold leading-snug tracking-[-0.01em]">{info.title}</h2>

      <div className="mt-v10 flex items-center gap-2.5">
        <span className="h-[22px] w-[22px] shrink-0 rounded-full bg-chip" />
        <span className="text-sm font-semibold">{info.author}</span>
        <span className="text-sm text-muted">·</span>
        <span className="text-sm font-medium text-muted">{info.sourceLabel}</span>
      </div>

      <button
        type="button"
        className="mt-v16 flex h-[46px] w-full items-center justify-center gap-2.5 rounded-[13px] border border-line bg-surface text-sm font-semibold text-ink transition-colors hover:bg-surface-2"
      >
        <ImageIcon />
        Kapak görselini indir
        {info.thumbnailWidth && info.thumbnailHeight
          ? ' · ' + info.thumbnailWidth + '×' + info.thumbnailHeight
          : ''}
      </button>
    </section>
  );
}
