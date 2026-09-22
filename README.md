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

Tasarımın doğal yüksekliği ~1050 px. 27" bir monitörde bu zaten sığıyor, ama
laptop (~930 px) ve MacBook (~760 px) ekranlarında taşıyordu.

Çözüm sayfayı küçültmek **değil** — o zaman gövde metni 11 px'e düşer ve
okunmaz. Bunun yerine yerin çoğunu tüketen şey daraltılıyor: boşluklar ve
dekoratif blok yükseklikleri. Tipografi ve dokunma hedefleri sabit kalır.

`src/index.css` içindeki `--spacing-v*` ölçeği bunu yapar:

```css
--spacing-v32: clamp(18px, 2.46vh, 32px);   /*  mt-8  -> mt-v32  */
--spacing-v40: clamp(22px, 3.08vh, 40px);   /*  mt-10 -> mt-v40  */
```

Ölçek katsayıları `tavan / 13` seçildi; yani 1300 px ekran yüksekliğinde hepsi
tavana oturur ve **büyük monitörde hiçbir şey değişmez.** Aynı mantık sabit
yükseklikli bloklara da uygulandı:

| | 27" (1340 px) | laptop (930 px) | MacBook (760 px) |
|---|---|---|---|
| header | 108 | 77 | 64 |
| boş durum kutusu | 400 | 286 | 234 |
| kalite satırı | 60 | 48 | 48 |
| başlık (h1) | 40 | 30 | 30 |
| gövde metni | 16 | 16 | 16 |
| **toplam sayfa** | **~1050** | **~817** | **~772** |

Sonuç: 930 px ve üzerinde kaydırma yok; 760 px'te yalnızca 5 kalite seçenekli
YouTube videosunda ~10 px kaydırma kalıyor. Metin hiçbir boyutta küçülmüyor.

Ayarlamak istersen tek yer `src/index.css` sonundaki `@theme` bloğu: tavanı
değiştirmek 27"deki görünümü, tabanı değiştirmek kısa ekranlardaki sıkılığı
belirler.

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
