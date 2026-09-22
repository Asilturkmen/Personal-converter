import { AudioIcon, VerticalVideoIcon, WideVideoIcon } from './Icons';
import type { ReactNode } from 'react';

const cards: { icon: ReactNode; title: string; body: string }[] = [
  { icon: <WideVideoIcon />, title: 'YouTube', body: 'Video, Shorts ve canlı yayın kaydı' },
  { icon: <VerticalVideoIcon />, title: 'Instagram', body: 'Reels, gönderi videoları ve hikâyeler' },
  { icon: <AudioIcon className="h-[18px] w-[18px]" />, title: 'MP3 dönüştürme', body: '128, 192, 256 ve 320 kbps' },
];

export default function SourceCards() {
  return (
    <div className="mt-v24 grid grid-cols-1 gap-v18 sm:grid-cols-3">
      {cards.map((card) => (
        <div
          key={card.title}
          className="flex min-h-[var(--h-card)] flex-col justify-between rounded-card border border-line bg-surface px-5 py-v20"
        >
          <span className="flex h-[34px] w-[34px] items-center justify-center rounded-[11px] bg-surface-2 text-ink">
            {card.icon}
          </span>
          <span className="mt-v16 flex flex-col gap-1">
            <span className="text-[15px] font-bold">{card.title}</span>
            <span className="text-[13.5px] font-medium text-muted">{card.body}</span>
          </span>
        </div>
      ))}
    </div>
  );
}
