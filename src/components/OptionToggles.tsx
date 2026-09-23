import type { AudioOptions } from '../types';

interface Props {
  options: AudioOptions;
  onChange: (options: AudioOptions) => void;
  disabled?: boolean;
}

const rowClass = 'flex items-center gap-3';
const boxClass = 'h-[19px] w-[19px] shrink-0 accent-[var(--color-accent)]';
const labelClass = 'text-[14.5px] font-semibold';

/** Yalnızca MP3 sekmesinde görünür; ikisi de dosyayı akış sırasında etiketler. */
export default function OptionToggles({ options, onChange, disabled = false }: Props) {
  return (
    <div className="mt-v20 flex flex-col gap-v14">
      <div className={rowClass}>
        <input
          id="option-cover"
          type="checkbox"
          className={boxClass}
          checked={options.cover}
          disabled={disabled}
          onChange={(event) => onChange({ ...options, cover: event.target.checked })}
        />
        <label htmlFor="option-cover" className={labelClass}>
          Kapak görselini MP3 etiketine göm
        </label>
      </div>

      <div className={rowClass}>
        <input
          id="option-tags"
          type="checkbox"
          className={boxClass}
          checked={options.tags}
          disabled={disabled}
          onChange={(event) => onChange({ ...options, tags: event.target.checked })}
        />
        <label htmlFor="option-tags" className={labelClass}>
          Başlık ve sanatçı etiketlerini doldur
        </label>
      </div>
    </div>
  );
}
