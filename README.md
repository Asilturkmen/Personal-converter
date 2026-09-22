```
 █████╗ ███████╗██╗██╗
██╔══██╗██╔════╝██║██║
███████║███████╗██║██║
██╔══██║╚════██║██║██║
██║  ██║███████║██║███████╗
╚═╝  ╚═╝╚══════╝╚═╝╚══════╝
   P E R S O N A L  ·  C O N V E R T E R
```

# Asil Personal-Converter

**Bağlantıyı yapıştır, MP4 ya da MP3 olarak indir.** Kişisel dönüştürücü arayüzü.

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
    Logo.tsx    Header.tsx  ThemeToggle.tsx  UrlInput.tsx
    ErrorNote.tsx
    MediaPreview.tsx  FormatTabs.tsx  QualityList.tsx
    OptionToggles.tsx  DownloadButton.tsx
    EmptyState.tsx  SourceCards.tsx  Footer.tsx  Icons.tsx
```

## Ekran yüksekliğine uyum

Tasarımın doğal yüksekliği ~1000 px. 1080p bir ekranda tarayıcı çubuklarından
sonra **925 px** viewport kalıyor, bir MacBook'ta ~760 px. Sabit px ölçülerle
ikisinde birden oturmuyordu.

Çözüm sayfayı `zoom` ile küçültmek **değil** — o zaman gövde metni 11 px'e
iner ve okunmaz. Bunun yerine yerin çoğunu tüketen şey daraltılıyor: boşluklar
ve dekoratif blok yükseklikleri. Gövde metni, etiketler ve dokunma hedefleri
hiçbir boyutta küçülmez.

`src/index.css` içinde tek bir ilerleme değeri her şeyi sürüyor:

```css
--fit: clamp(0px, calc((100vh - 760px) / 160), 1px);
/*  0px = 760 px viewport (tabanlar)   ·   1px = 920 px ve üzeri (tavanlar)  */

--h-empty: calc(250px + 80 * var(--fit));   /* 250 → 330 */
--spacing-v32: calc(18px + 14 * var(--fit));   /* mt-8 → mt-v32 */
```

Tek bir `Xvh` katsayısı yerine iki nokta arası geçiş kullanılıyor: `Xvh`
sıfırdan geçen bir doğru demek, yani bir uçta doğru olduğunda öteki uçta
şaşıyor. Burada kısa ekran ve büyük ekran ayrı ayrı ayarlanabiliyor.

| | 1080p (925 px) | MacBook (760 px) |
|---|---|---|
| header | 96 | 64 |
| boş durum kutusu | 330 | 250 |
| kalite satırı | 56 | 48 |
| başlık (h1) | 40 | 30 |
| gövde metni | 16 | 16 |
| **boş ekran toplamı** | **905** | **676** |

Footer `main`'in dışında duruyor ve `main` `grow` aldığı için sayfanın dibine
yapışır. Artan boşluk böylece footer'ın altında değil üstünde toplanır —
büyük monitörde sayfa yarım kalmış gibi görünmez.

Kaydırma durumu: boş ekranda hiçbir boyutta yok. Bağlantı getirildikten sonra
5 kalite seçenekli YouTube videosunda 925 px'te ~34 px kalıyor; Instagram ve
MP3 listelerinde yok.

**Ayar:** her şey `src/index.css` başındaki `:root` bloğunda. Soldaki sayı
kısa ekranı, sağdaki büyük ekranı belirler; `160` ise geçişin tamamlandığı
yüksekliği (760 + 160 = 920 px). Başka dosyaya dokunmaya gerek yok.

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
