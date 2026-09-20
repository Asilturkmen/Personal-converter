import { DownloadIcon } from './Icons';
import ThemeToggle from './ThemeToggle';
import type { Theme } from '../hooks/useTheme';

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
}

export default function Header({ theme, onToggleTheme }: Props) {
  return (
    <header className="border-b border-line-soft bg-header">
      <div className="mx-auto flex h-[68px] max-w-[1120px] items-center justify-between px-5 md:h-[76px] md:px-10">
        <div className="flex items-center gap-[11px]">
          <span className="flex h-[30px] w-[30px] items-center justify-center rounded-[9px] bg-accent text-white">
            <DownloadIcon className="h-4 w-4" />
          </span>
          <span className="text-[19px] font-extrabold tracking-[-0.02em]">Arşiv</span>
        </div>

        <div className="flex items-center gap-3.5">
          <span className="hidden text-[13px] font-medium text-muted sm:inline">kişisel indirme aracı</span>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  );
}
