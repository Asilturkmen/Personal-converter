type IconProps = { className?: string };

const base = 'shrink-0';

export function DownloadIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 4v11" />
      <path d="M7 11l5 5 5-5" />
      <path d="M5 20h14" />
    </svg>
  );
}

export function SunIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4" />
    </svg>
  );
}

export function MoonIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 14.5A8.2 8.2 0 1 1 9.5 4a6.6 6.6 0 0 0 10.5 10.5z" />
    </svg>
  );
}

export function ClipboardIcon({ className = 'h-4 w-4' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="8" y="3" width="8" height="4" rx="1.4" />
      <path d="M16 5h2a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2" />
    </svg>
  );
}

export function LinkIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 13.5a4 4 0 0 0 5.7.4l2.8-2.8a4 4 0 0 0-5.6-5.7l-1.4 1.4" />
      <path d="M14 10.5a4 4 0 0 0-5.7-.4l-2.8 2.8a4 4 0 0 0 5.6 5.7l1.4-1.4" />
    </svg>
  );
}

export function PlayIcon({ className = 'h-5 w-5' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M8 5.5v13l11-6.5z" />
    </svg>
  );
}

export function VideoIcon({ className = 'h-[17px] w-[17px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2.5" y="5.5" width="14" height="13" rx="3" />
      <path d="M16.5 10.5l5-3v9l-5-3z" />
    </svg>
  );
}

export function AudioIcon({ className = 'h-[17px] w-[17px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 18V6l10-2v12" />
      <circle cx="6.5" cy="18" r="2.6" />
      <circle cx="16.5" cy="16" r="2.6" />
    </svg>
  );
}

export function ImageIcon({ className = 'h-4 w-4' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="4" width="18" height="16" rx="3" />
      <circle cx="8.5" cy="9.5" r="1.6" />
      <path d="M4 17l5-5 4 4 3-2.5 4 3.5" />
    </svg>
  );
}

export function ArrowRightIcon({ className = 'h-[17px] w-[17px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12h13" />
      <path d="M13 6l6 6-6 6" />
    </svg>
  );
}

export function VerticalVideoIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="6.5" y="2.5" width="11" height="19" rx="3.5" />
      <path d="M10.5 9.5l4.5 2.5-4.5 2.5z" />
    </svg>
  );
}

export function WideVideoIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2.5" y="5" width="19" height="14" rx="4" />
      <path d="M10.5 9.5l5 2.5-5 2.5z" />
    </svg>
  );
}

export function SpinnerIcon({ className = 'h-[18px] w-[18px]' }: IconProps) {
  return (
    <svg className={base + ' ' + className + ' animate-spin'} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth={2.4} opacity={0.25} />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" />
    </svg>
  );
}
