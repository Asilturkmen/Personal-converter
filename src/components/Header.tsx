import Logo from './Logo';
import ThemeToggle from './ThemeToggle';
import type { Theme } from '../hooks/useTheme';

interface Props {
  theme: Theme;
  onToggleTheme: () => void;
}

export default function Header({ theme, onToggleTheme }: Props) {
  return (
    <header className="border-b border-line-soft bg-header">
      <div className="mx-auto flex h-[88px] max-w-[1120px] items-center justify-between px-5 md:h-[var(--h-header)] md:px-10">
        <Logo />

        <div className="flex items-center gap-3.5">
          <span className="hidden text-[13px] font-medium text-muted sm:inline">kişisel indirme aracı</span>
          <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        </div>
      </div>
    </header>
  );
}
