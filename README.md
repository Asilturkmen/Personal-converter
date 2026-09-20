# Arşiv — video ve MP3 indirici (ön yüz)

React + TypeScript + Vite + Tailwind CSS v4. Tasarım tuvalindeki dört artboard'un
çalışan karşılığı: açık/koyu tema, MP4/MP3 sekmesi, kalite seçimi, altyazı ve
kapak seçenekleri, mobil yerleşim.

Şu an tüm veriler sahte. Arka uç yazıldığında tek bir dosya değişiyor: `src/lib/api.ts`.

## Kurulum

```bash
npm install
npm run dev
```

Tarayıcı `http://localhost:5173` adresini açar. Üretim derlemesi için `npm run build`.

## Klasör yapısı

```
src/
  App.tsx                 durum yönetimi ve sayfa yerleşimi
  types.ts                MediaInfo, QualityOption, DownloadRequest tipleri
  index.css               tasarım token'ları (tek renk kaynağı)
  lib/
    api.ts                SAHTE API — gerçek fetch çağrıları buraya gelecek
    format.ts             bayt ve süre biçimlendirme
  hooks/
    useTheme.ts           açık/koyu tema, localStorage'da hatırlanır
    useClipboardPaste.ts  panodan yapıştırma
  components/
    Header.tsx  ThemeToggle.tsx  UrlInput.tsx  ErrorNote.tsx
    MediaPreview.tsx  FormatTabs.tsx  QualityList.tsx
    OptionToggles.tsx  DownloadButton.tsx
    EmptyState.tsx  SourceCards.tsx  Footer.tsx  Icons.tsx
```

## Renkleri değiştirmek

Tailwind v4 kullanılıyor, yani ayrı bir `tailwind.config.js` yok. Bütün token'lar
`src/index.css` içindeki `@theme` bloğunda:

```css
@theme {
  --color-accent: #2f6be0;   /* -> bg-accent, text-accent, border-accent */
  --color-surface: #ffffff;  /* -> bg-surface ... */
  --radius-card: 18px;       /* -> rounded-card */
}
```

Aynı değişkenler hemen altındaki `.dark { ... }` bloğunda koyu tema değerleriyle
yeniden tanımlı. Vurgu rengini değiştirmek istersen `--color-accent` ve
`--color-accent-strong` satırlarını düzenlemen yeterli; geçtiği her yerde değişir.

## Arka uca bağlarken

`src/lib/api.ts` içindeki iki fonksiyonun gövdesini değiştir. Dosyanın sonunda
gerçek `fetch` karşılıkları yorum olarak duruyor. Beklenen JSON şekli `types.ts`
içindeki `MediaInfo` ve `DownloadTicket` tipleri.

Özetle:

- `GET /api/info?url=...` → `MediaInfo`
- `POST /api/download` (gövde: `DownloadRequest`) → `DownloadTicket`

Arka uç tarafında video çözümlemesi için `yt-dlp`, MP3'e çevirme için `ffmpeg`
tipik seçimler.

## Erişilebilirlik notları

- Kalite listesi gerçek `radio` girdileriyle yazıldı, klavyeyle gezilebilir.
- Tüm dokunma hedefleri en az 44 px.
- Yalnızca ikon içeren butonlarda `aria-label` var.
- Tema `color-scheme` ile birlikte değişir, form denetimleri de uyum sağlar.
