import { useId } from 'react';

const LINK_A = { x: 10.3, y: 19.4, w: 18.75, h: 9.25, r: 4.63 };
const LINK_B = { x: 18.9, y: 19.4, w: 18.75, h: 9.25, r: 4.63 };
const CHAIN = 'translate(0 -7) rotate(-45 24 24)';
const STROKE = 4.35;
const ARROW = 'M21 24h6v12h5.5L24 46l-8.5-10H21z';

/**
 * AMBLEM
 * İki halkalı zincir + aşağı bakan ok. Zincir `currentColor` kullanıyor,
 * yani metin rengini (ink) alıyor ve koyu temada kendiliğinden açılıyor.
 * Ok her iki temada da accent renginde kalıyor.
 * Halkaların geçme yerlerindeki boşluklar maske ile açılıyor — arka plan
 * rengine bağlı değil, her zeminde temiz durur.
 */
export function LogoMark({ className = 'h-[48px]' }: { className?: string }) {
  const uid = useId().replace(/:/g, '');
  const [mA, mB, mArrow, clipTop, clipBottom] = [
    `${uid}-a`, `${uid}-b`, `${uid}-ar`, `${uid}-ct`, `${uid}-cb`,
  ];

  return (
    <svg viewBox="7.4 0.5 33.2 46.8" className={'aspect-[332/468] w-auto shrink-0 ' + className} fill="none" aria-hidden="true">
      <defs>
        <clipPath id={clipTop}><rect x="0" y="0" width="48" height="24" /></clipPath>
        <clipPath id={clipBottom}><rect x="0" y="24" width="48" height="24" /></clipPath>

        {/* alttaki halkadan, üstteki halkanın geçtiği yerde boşluk aç */}
        <mask id={mA} maskUnits="userSpaceOnUse" x="-8" y="-8" width="64" height="64">
          <rect x="-8" y="-8" width="64" height="64" fill="#fff" />
          <g clipPath={`url(#${clipBottom})`}>
            <rect {...rectProps(LINK_B)} stroke="#000" strokeWidth={8.15} />
          </g>
        </mask>

        <mask id={mB} maskUnits="userSpaceOnUse" x="-8" y="-8" width="64" height="64">
          <rect x="-8" y="-8" width="64" height="64" fill="#fff" />
          <g clipPath={`url(#${clipTop})`}>
            <rect {...rectProps(LINK_A)} stroke="#000" strokeWidth={8.15} />
          </g>
        </mask>

        {/* ok zincirin arkasından çıkıyor: zincirin silueti oktan kesiliyor */}
        <mask id={mArrow} maskUnits="userSpaceOnUse" x="-8" y="-8" width="64" height="64">
          <rect x="-8" y="-8" width="64" height="64" fill="#fff" />
          <g transform={CHAIN} stroke="#000" strokeWidth={6.8} fill="none">
            <rect {...rectProps(LINK_A)} />
            <rect {...rectProps(LINK_B)} />
          </g>
        </mask>
      </defs>

      <path
        d={ARROW}
        mask={`url(#${mArrow})`}
        className="fill-accent stroke-accent"
        strokeWidth={1.4}
        strokeLinejoin="round"
      />

      <g transform={CHAIN} stroke="currentColor" strokeWidth={STROKE} fill="none">
        <rect {...rectProps(LINK_A)} mask={`url(#${mA})`} />
        <rect {...rectProps(LINK_B)} mask={`url(#${mB})`} />
      </g>
    </svg>
  );
}

function rectProps({ x, y, w, h, r }: { x: number; y: number; w: number; h: number; r: number }) {
  return { x, y, width: w, height: h, rx: r, fill: 'none' as const };
}

/**
 * KİLİT (amblem + kelime markası)
 * Yatay tek satır: amblem, "Asil", ince ayraç, tanım satırı. Header yatay bir
 * bant olduğu için kilit de yatay — böylece 64px'e inen kısa ekran header'ında
 * bile sıkışmıyor. (Önceki iki katlı dizilişte tanım satırı kelime markasından
 * üç kat genişti ve kilidi dengesiz gösteriyordu.)
 *
 * Amblem yüksekliği header ile aynı oranda daralıyor: 96px'lik header'da
 * 54px, 64px'lik header'da 34px. Genişlik viewBox oranından kendiliğinden geliyor (bkz. aspect-*).
 * Kelime markası 36px'in altına 30px'ten fazla inmiyor — okunabilirlik önce.
 *
 * Tanım satırı yalnızca sm ve üzerinde görünür; telefonda amblem + "Asil"
 * kalır, header'ın sağındaki "kişisel indirme aracı" zaten aynı işi görür.
 *
 * Ortadaki nokta, amblemdeki okla aynı accent rengini taşıyor — iki parçayı
 * birbirine bağlayan tek detay bu. Büyük harfler CSS `uppercase` yerine
 * doğrudan yazıldı: lang="tr" altında text-transform "i" harfini "İ" yapar.
 */
export default function Logo({ className = '' }: { className?: string }) {
  return (
    <span className={'flex items-center gap-[14px] text-ink ' + className}>
      <LogoMark className="h-[52px] md:h-[var(--h-logo)]" />

      <span className="flex items-center gap-[14px]">
        <span className="text-[30px] font-extrabold leading-none tracking-[-0.035em] md:text-[length:var(--t-logo)]">
          Asil
        </span>

        <span aria-hidden="true" className="hidden h-[24px] w-px bg-line sm:block" />

        <span className="hidden text-[10.5px] font-bold leading-none tracking-[0.24em] text-muted sm:block">
          PERSONAL<span className="mx-[0.55em] text-accent">·</span>CONVERTER
        </span>
      </span>
    </span>
  );
}
