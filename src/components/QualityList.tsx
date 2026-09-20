import { formatBytes } from '../lib/format';
import type { QualityOption } from '../types';

interface Props {
  options: QualityOption[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  legend: string;
}

export default function QualityList({ options, selectedId, onSelect, legend }: Props) {
  return (
    <fieldset className="mt-6 border-0 p-0">
      <div className="flex items-baseline justify-between">
        <legend className="float-left text-xs font-bold uppercase tracking-[0.09em] text-muted">{legend}</legend>
        <span className="text-[13px] font-medium text-muted">tahmini boyut</span>
      </div>

      <div className="mt-2.5 overflow-hidden rounded-card border border-line bg-surface shadow-soft">
        {options.map((option, index) => {
          const selected = option.id === selectedId;
          const last = index === options.length - 1;

          return (
            <label
              key={option.id}
              className={
                'flex h-[60px] cursor-pointer items-center justify-between px-[18px] transition-colors focus-within:outline-2 focus-within:outline-offset-[-2px] focus-within:outline-accent ' +
                (last ? '' : 'border-b border-line-soft ') +
                (selected ? 'bg-pick' : 'hover:bg-surface-2')
              }
            >
              <input
                type="radio"
                name="quality"
                value={option.id}
                checked={selected}
                onChange={() => onSelect(option.id)}
                className="sr-only"
              />

              <span className="flex flex-col gap-0.5">
                <span className="text-[15px] font-bold">{option.label}</span>
                <span className="text-[12.5px] font-medium text-muted">{option.sub}</span>
              </span>

              <span className="flex items-center gap-4">
                <span className="text-[13px] font-semibold text-muted">{formatBytes(option.sizeBytes)}</span>
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
