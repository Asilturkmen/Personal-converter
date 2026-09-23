import { useState } from 'react';
import { ImageIcon, PlayIcon } from './Icons';
import { formatDuration, platformLabel } from '../lib/format';
import type { MediaInfo } from '../types';

interface Props {
  info: MediaInfo;
}

export default function MediaPreview({ info }: Props) {
  const [broken, setBroken] = useState(false);
  const vertical = !!info.width && !!info.height && info.height > info.width;
  const showImage = !!info.thumbnail && !broken;

  return (
    <section>
      {/*
        Kutu her zaman 16:9 kalır, böylece dikey videoda sayfa uzamaz. Dikey
        videoda kapak kendi oranında (ör. 9:16) ortalanır, arkasında aynı
        görselin bulanık hâli durur. Kapak dikeyse hiçbir şey kırpılmaz;
        YouTube'un yanlarına siyah bant eklediği yatay kapaklarda yalnızca
        bantlar kırpılır.
      */}
      <div className="relative aspect-video w-full overflow-hidden rounded-card border border-line bg-thumb">
        {/* Yer tutucu hep altta: kapak yüklenirken ya da hiç yoksa görünür. */}
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5">
          <span className="flex h-[54px] w-[54px] items-center justify-center rounded-full bg-surface shadow-soft">
            <PlayIcon />
          </span>
          {!showImage && <span className="text-xs font-semibold tracking-[0.08em] text-thumb-ink">KAPAK YOK</span>}
        </div>

        {showImage && vertical && (
          <>
            <img
              src={info.thumbnail!}
              alt=""
              aria-hidden="true"
              className="absolute inset-0 h-full w-full scale-110 object-cover opacity-60 blur-2xl"
            />
            <img
              src={info.thumbnail!}
              alt=""
              onError={() => setBroken(true)}
              style={{ aspectRatio: `${info.width} / ${info.height}` }}
              className="relative mx-auto h-full object-cover shadow-soft"
            />
          </>
        )}

        {showImage && !vertical && (
          <img src={info.thumbnail!} alt="" onError={() => setBroken(true)} className="relative h-full w-full object-cover" />
        )}

        <span className="absolute left-3.5 top-3.5 rounded-full bg-surface/90 px-2.5 py-1.5 text-xs font-bold text-ink backdrop-blur">
          {platformLabel(info.source)}
        </span>
        {info.duration > 0 && (
          <span className="absolute bottom-3.5 right-3.5 rounded-lg bg-black/75 px-2.5 py-1 text-xs font-bold text-white">
            {formatDuration(info.duration)}
          </span>
        )}
      </div>

      <h2 className="mt-v16 line-clamp-2 text-[19px] font-bold leading-snug tracking-[-0.01em]" title={info.title}>
        {info.title}
      </h2>

      <div className="mt-v10 flex min-w-0 items-center gap-2.5">
        <span className="h-[22px] w-[22px] shrink-0 rounded-full bg-chip" />
        {info.uploader && <span className="truncate text-sm font-semibold">{info.uploader}</span>}
        {info.uploader && info.width && info.height && <span className="text-sm text-muted">·</span>}
        {info.width && info.height && (
          <span className="shrink-0 text-sm font-medium text-muted">
            {info.width}×{info.height} kaynak
          </span>
        )}
      </div>

      {showImage && (
        <a
          href={info.thumbnail + '&download=1'}
          download
          className="mt-v16 flex h-[46px] w-full items-center justify-center gap-2.5 rounded-[13px] border border-line bg-surface text-sm font-semibold text-ink transition-colors hover:bg-surface-2"
        >
          <ImageIcon />
          Kapak görselini indir
        </a>
      )}
    </section>
  );
}
