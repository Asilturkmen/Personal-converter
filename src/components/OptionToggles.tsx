import type { Mode } from '../types';

interface Props {
  mode: Mode;
  subtitles: boolean;
  cover: boolean;
  subtitlesAvailable: boolean;
  onSubtitlesChange: (value: boolean) => void;
  onCoverChange: (value: boolean) => void;
}

const rowClass = 'flex items-center gap-3';
const boxClass = 'h-[19px] w-[19px] shrink-0 accent-[var(--color-accent)]';
const labelClass = 'text-[14.5px] font-semibold';

export default function OptionToggles({
  mode,
  subtitles,
  cover,
  subtitlesAvailable,
  onSubtitlesChange,
  onCoverChange,
}: Props) {
  const isVideo = mode === 'video';

  return (
    <div className="mt-v20 flex flex-col gap-v14">
      <div className={rowClass}>
        <input
          id="option-one"
          type="checkbox"
          className={boxClass}
          checked={isVideo ? subtitles : cover}
          disabled={isVideo && !subtitlesAvailable}
          onChange={(event) => (isVideo ? onSubtitlesChange(event.target.checked) : onCoverChange(event.target.checked))}
        />
        <label htmlFor="option-one" className={labelClass + (isVideo && !subtitlesAvailable ? ' text-muted' : '')}>
          {isVideo ? 'Altyazıyı da indir (.srt)' : 'Kapak görselini MP3 etiketine göm'}
        </label>
      </div>

      <div className={rowClass}>
        <input
          id="option-two"
          type="checkbox"
          className={boxClass}
          checked={isVideo ? cover : subtitles}
          onChange={(event) => (isVideo ? onCoverChange(event.target.checked) : onSubtitlesChange(event.target.checked))}
        />
        <label htmlFor="option-two" className={labelClass}>
          {isVideo ? 'Kapak görselini ayrı dosya olarak kaydet' : 'Başlık ve sanatçı etiketlerini doldur'}
        </label>
      </div>
    </div>
  );
}
