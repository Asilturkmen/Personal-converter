import type { ClipboardEvent, FormEvent } from 'react';
import { ArrowRightIcon, ClipboardIcon, LinkIcon, SpinnerIcon } from './Icons';
import { useClipboardPaste } from '../hooks/useClipboardPaste';

interface Props {
  value: string;
  onChange: (value: string) => void;
  /** Getir'e basınca ya da bir bağlantı yapıştırılınca çağrılır. */
  onSubmit: (url: string) => void;
  loading: boolean;
}

export default function UrlInput({ value, onChange, onSubmit, loading }: Props) {
  const { paste, denied } = useClipboardPaste((text) => {
    onChange(text);
    if (!loading) onSubmit(text);
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!loading && value.trim()) onSubmit(value.trim());
  }

  // Kutu boşken ya da tamamı seçiliyken yapıştırılan bağlantı hemen getirilir.
  // Var olan metnin ortasına yapıştırma (düzeltme) normal davranır.
  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const replacesAll = input.selectionStart === 0 && input.selectionEnd === input.value.length;
    const text = event.clipboardData.getData('text').trim();
    if (!replacesAll || !text || loading) return;

    event.preventDefault();
    onChange(text);
    onSubmit(text);
  }

  return (
    <div>
      <form
        onSubmit={handleSubmit}
        className="flex items-center gap-2 rounded-card border border-line bg-surface p-1.5 pl-3.5 shadow-soft sm:gap-3 sm:p-2 sm:pl-5"
      >
        <LinkIcon className="hidden h-[18px] w-[18px] text-muted sm:block" />

        <label htmlFor="media-url" className="sr-only">
          Video bağlantısı
        </label>
        <input
          id="media-url"
          type="url"
          inputMode="url"
          autoComplete="off"
          spellCheck={false}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onPaste={handlePaste}
          placeholder="Bağlantıyı buraya yapıştır"
          className="h-11 min-w-0 grow bg-transparent text-[15px] font-medium text-ink outline-none placeholder:text-muted sm:text-base"
        />

        <button
          type="button"
          onClick={paste}
          aria-label="Panodan yapıştır"
          className="flex h-11 shrink-0 items-center justify-center gap-2 rounded-[11px] bg-chip px-3 text-sm font-semibold text-ink transition-colors hover:brightness-95 sm:px-4"
        >
          <ClipboardIcon />
          <span className="hidden sm:inline">Yapıştır</span>
        </button>

        <button
          type="submit"
          disabled={loading || !value.trim()}
          className="flex h-11 shrink-0 items-center justify-center gap-2 rounded-[11px] bg-accent px-3 text-[15px] font-bold text-white transition-colors hover:bg-accent-strong disabled:cursor-not-allowed disabled:opacity-50 sm:px-6"
        >
          {loading ? <SpinnerIcon /> : <ArrowRightIcon className="h-[17px] w-[17px] sm:hidden" />}
          <span className="hidden sm:inline">{loading ? 'Getiriliyor' : 'Getir'}</span>
        </button>
      </form>

      {denied && (
        <p role="alert" className="mt-2 text-[13px] font-medium text-muted">
          Tarayıcı pano erişimine izin vermedi. Bağlantıyı kutuya elle yapıştır (Ctrl+V ya da uzun bas → Yapıştır).
        </p>
      )}
    </div>
  );
}
