import { formatEstimate, qualityNote } from '../lib/format';
import type { MediaFormat } from '../types';

interface Props {
  formats: MediaFormat[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  legend: string;
  disabled?: boolean;
}

function subLabel(format: MediaFormat): string {
  if (format.kind === 'audio') return '~190 kbps · en iyi ses kaynağından';
  return qualityNote(format.height, format.fps, format.codec) || 'MP4';
}

export default function QualityList({ formats, selectedId, onSelect, legend, disabled = false }: Props) {
  return (
    <fieldset className="mt-v24 border-0 p-0" disabled={disabled}>
      <div className="flex items-baseline justify-between">
        <legend className="float-left text-xs font-bold uppercase tracking-[0.09em] text-muted">{legend}</legend>
        <span className="text-[13px] font-medium text-muted">tahmini boyut</span>
      </div>

      <div className="mt-v10 overflow-hidden rounded-card border border-line bg-surface shadow-soft">
        {formats.map((format, index) => {
          const selected = format.id === selectedId;
          const last = index === formats.length - 1;

          return (
            <label
              key={format.id}
              className={
                'flex h-[var(--h-row)] cursor-pointer items-center justify-between px-[18px] transition-colors focus-within:outline-2 focus-within:outline-offset-[-2px] focus-within:outline-accent ' +
                (last ? '' : 'border-b border-line-soft ') +
                (selected ? 'bg-pick' : 'hover:bg-surface-2')
              }
            >
              <input
                type="radio"
                name="quality"
                value={format.id}
                checked={selected}
                onChange={() => onSelect(format.id)}
                className="sr-only"
              />

              <span className="flex flex-col gap-0.5">
                <span className="text-[15px] font-bold">{format.label}</span>
                <span className="text-[12.5px] font-medium text-muted">{subLabel(format)}</span>
              </span>

              <span className="flex items-center gap-4">
                <span className="text-[13px] font-semibold text-muted">{formatEstimate(format.estimatedBytes)}</span>
                <span
                  aria-hidden="true"
                  className={
                    'flex h-5 w-5 items-center justify-center rounded-full border-2 ' +
                    (selected ? 'border-accent' : 'border-line')
                  }
                >
                  <span className={'h-2.5 w-2.5 rounded-full bg-accent ' + (selected ? 'opacity-100' : 'opacity-0')} />
                </span>
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
