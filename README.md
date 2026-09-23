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

**Bağlantıyı yapıştır, MP4 ya da MP3 olarak indir.** YouTube (video, Shorts) ve
Instagram (reels, gönderi videoları, hikâyeler) için kişisel indirme aracı.

- **Frontend:** React + TypeScript + Vite + Tailwind CSS v4 — kök dizinde
- **Backend:** Python + FastAPI + yt-dlp + ffmpeg — `backend/` klasöründe

```
yt-dlp (metadata + CDN adresleri)  →  ffmpeg (CDN'den okur, stdout'a yazar)  →  HTTP yanıtı
```

**Değişmez kural:** sunucunun diskine hiçbir zaman hiçbir dosya yazılmaz. Geçici
dosya, temp klasörü, kuyruk klasörü yok; video verisi sunucudan yalnızca akarak geçer.

## Windows'ta kurulum

Gerekenler (PATH'te): **Python 3.12+**, **ffmpeg**, **Deno**, **Node**.

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Gyan.FFmpeg
winget install -e --id DenoLand.Deno
```

Kurulumdan sonra PowerShell'i kapatıp yeniden aç, sonra kontrol et:
`python --version`, `ffmpeg -version`, `deno --version`, `node --version`.

> **Deno neden şart?** yt-dlp YouTube'un imza şifresini çözmek için bir
> JavaScript runtime çalıştırıyor, varsayılanı Deno. Bulamazsa formatların
> çoğu eksik gelir. Backend açılışta kontrol eder ve konsola uyarı basar;
> `/api/health` yanıtındaki `jsRuntime` alanı `"deno"` göstermeli.

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --port 8000
```

`Activate.ps1` "running scripts is disabled on this system" hatası verirse
PowerShell'de bir kez şunu çalıştır, sonra tekrar dene:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Geliştirirken `uvicorn app:app --port 8000 --reload --reload-exclude .venv`
ile kod değiştikçe kendini yeniden başlatır.

### Frontend

Ayrı bir terminalde, proje kökünde:

```powershell
npm install
npm run dev
```

`http://localhost:5173` adresini aç. `/api` istekleri Vite proxy'si ile
backend'e (`127.0.0.1:8000`) gider — CORS yok, yollar sunucuda da aynı kalır.

### Ayarlar (.env)

Hepsi isteğe bağlı. `backend/.env.example` dosyasını `backend/.env` olarak
kopyalayıp değiştirmek istediğin satırları aç.

| Değişken | Varsayılan | |
|---|---|---|
| `ALLOWED_HOSTS` | youtube.com, youtu.be, m.youtube.com, music.youtube.com, instagram.com | www. alt alan adları otomatik |
| `MAX_HEIGHT` / `MIN_HEIGHT` | 1080 / 360 | kısa kenara göre |
| `MAX_DURATION_MINUTES` | 90 | |
| `MAX_MEGABYTES` | 2048 | ön kontrol + akış sırasında bayt sayacı |
| `DOWNLOAD_TIMEOUT_MINUTES` | 15 | aşılırsa ffmpeg öldürülür |
| `MAX_CONCURRENT_DOWNLOADS` | 3 | dolu → 503, kuyruk yok |
| `MAX_CONCURRENT_INFO` | 2 | link çözümleme CPU yiyor, ayrı sınır |
| `MAX_DOWNLOADS_PER_IP` | 1 | 0 = sınırsız (test için) |
| `CACHE_TTL_MINUTES` / `CACHE_MAX_ENTRIES` | 25 / 200 | video kimliği bazında |
| `INSTAGRAM_COOKIES` | `./cookies.txt` | göreli yol `backend/`'e göre |
| `FFMPEG_PATH` / `FFPROBE_PATH` | ffmpeg / ffprobe | PATH'te değilse tam yol |

### Instagram çerezleri (hikâyeler için)

Reels ve gönderi videoları çoğunlukla çerezsiz çalışır; **hikâyeler çerez olmadan
çalışmaz.** Çerez için:

1. Tarayıcına "Get cookies.txt LOCALLY" eklentisini kur.
2. **Çöp bir Instagram hesabıyla** giriş yap (ana hesabını kullanma, kapanabilir).
3. instagram.com'dayken eklentiyle `cookies.txt` indir, `backend/cookies.txt` olarak koy.
4. Backend'i yeniden başlatmana gerek yok; her istekte dosya okunur.

Çerez düzenli olarak düşer. "Instagram oturumu gerekli veya süresi dolmuş —
cookies.txt yenilenmeli." hatası görürsen dosyayı yenile. Dosya salt okunur
kullanılır, yt-dlp'nin üzerine yazması engellenmiştir.

### yt-dlp'yi güncellemek

YouTube ayda birkaç kez bir şeyi kırıyor. İndirme bozulursa **ilk yapılacak şey**:

```powershell
cd backend
.venv\Scripts\Activate.ps1
pip install -U "yt-dlp[default]"
```

## API

| | |
|---|---|
| `GET /api/info?url=` | başlık, kanal, süre, kapak ve hazır format listesi (`mp3`, `v360` … `v1080`) |
| `GET /api/download?url=&format=[&cover=1&tags=1]` | dosyayı akıtır; `cover`/`tags` yalnızca MP3 için |
| `GET /api/thumbnail?url=[&download=1]` | kapak görseli (Instagram CDN'i başka origin'e görsel vermediği için backend üzerinden) |
| `GET /api/health` | `{"ok": true, "ytDlp": "...", "jsRuntime": "deno"}` |

Hatalar `{"detail": "Türkçe mesaj"}` biçiminde döner; teknik ayrıntı yalnızca konsola loglanır.
`/api/download` bilerek `Content-Length` göndermez (tahmin saparsa indirme bozulur);
tahmini boyut `X-Estimated-Bytes` başlığındadır.

## Backend nasıl çalışıyor

```
backend/
  app.py        FastAPI uçları, sınırlar, akış yanıtı
  config.py     .env ayarları
  media.py      yt-dlp çözümleme, format seçimi, önbellek, Türkçe hata mesajları
  stream.py     ffmpeg komutu ve süreç yönetimi
  relay.py      YouTube akışlarını parça parça okuyan bellek içi köprü
  tags.py       MP3 ID3 etiketi (başlık, sanatçı, kapak) — bellekte
  limits.py     slot sayaçları
  names.py      dosya adı temizliği, RFC 5987 Content-Disposition
```

**Format seçimi.** Video çözünürlüğü `min(genişlik, yükseklik)` ile belirlenir —
dikey bir Shorts'ta 1080p = 1080×1920. Aynı çözünürlükte H.264 (avc1) tercih
edilir; bazı telefonlar AV1'i açamıyor. Video ve ses ayrıysa ffmpeg iki girdiyi
`-c copy` ile birleştirir, **yeniden kodlama yok.** Çıktı parçalı mp4
(`frag_keyframe+empty_moov+default_base_moof`), çünkü normal mp4 başına yazılacak
`moov` için dosyanın sonunu bekler. MP3 tek seçenek: en iyi ses akışı
`libmp3lame -q:a 2` (VBR, ~190 kbps).

**Neden `asyncio.create_subprocess_exec` değil?** Windows'ta uvicorn (özellikle
`--reload` ile) SelectorEventLoop kullanır ve asyncio'nun alt süreç API'si orada
`NotImplementedError` fırlatır. Bu yüzden `subprocess.Popen` kullanılıyor; bloklayan
stdout okumaları thread havuzunda yapılıyor, event loop bloklanmıyor. Aynı kod
Linux'ta değişmeden çalışır. `--reload` altında test edildi.

**Relay (YouTube hızı).** YouTube, bir akışı tek uzun istekle okuyanı ilk ~10 MB'tan
sonra gerçek zamana yakın hıza düşürüyor (ölçülen: 0,2–0,3 MB/s). yt-dlp bu yüzden
10 MB'lık `range` parçalarıyla indiriyor ama ffmpeg bunu yapamıyor. Çözüm:
ffmpeg'e CDN adresi yerine backend'in loopback üzerindeki
`/internal/relay/<token>` adresi veriliyor; bu uç CDN'den parçaları sırayla çekip
ffmpeg'e tek akış olarak geçiriyor. Tamamen bellekte, adlandırılmış pipe gerektirmiyor,
Windows ve Linux'ta aynı. Sonuç: hat hızında indirme ve bayt bayt doğru boyut tahmini.
Token rastgele ve yalnızca indirme sürerken geçerli; uç `/api` dışında olduğu için
dışarıya proxy'lenmez.

**MP3 etiketleri.** ffmpeg pipe'a yazarken ID3 etiketinin boyut alanını dolduramıyor
(sona gelip geri dönmesi gerekir), boyut 0 kalınca oynatıcılar kapağı ve başlığı
görmüyor. Bu yüzden ffmpeg etiketsiz ham MP3 üretiyor ve ID3v2.3 etiketi `mutagen` ile
bellekte oluşturulup akışın başına ekleniyor. WebP kapaklar bellekte JPEG'e çevriliyor.

**Sınırlar.** Canlı yayınlar reddedilir (sonu olmayan akış slotu sonsuza kadar kilitler).
Boyut sınırı hem tahminle hem akış sırasında gerçek bayt sayacıyla kontrol edilir;
sayaç aşılırsa ffmpeg öldürülür. İstemci bağlantıyı koparırsa (sekme kapandı, iptal)
ffmpeg öldürülür ve relay durur. Aynı videoya aynı anda gelen çözümleme istekleri
tek bir yt-dlp çağrısında birleştirilir.

## Frontend: indirme ve ilerleme

İndirme üç katmanlı, sırayla (`src/lib/api.ts`):

1. **`showSaveFilePicker` varsa** (Chrome, Edge): konum sorulur, akış doğrudan
   dosyaya yazılır, RAM'de birikmez. Picker tıklamadan hemen sonra, herhangi bir
   `await`'ten önce açılır; iptal edilirse sessizce çıkılır.
2. **Yoksa ve dosya 250 MB'tan küçükse** (Brave varsayılanda, Firefox, Safari):
   akış okunur, ilerleme gösterilir, parçalar Blob'da toplanıp kaydedilir.
3. **Diğer durumlarda:** tarayıcının kendi indiricisine devredilir; arayüz
   "İndirme tarayıcıya devredildi" yazar. Büyük dosya telefonda belleği patlatmasın.

Yüzde `X-Estimated-Bytes` ile hesaplanır, akış bitene kadar %99'da sabitlenir.
Sunucu 200 döndükten sonra akış kesilirse indirme başarısız sayılır — yarım dosya
başarılı gösterilmez.

## Frontend klasör yapısı

```
src/
  App.tsx                 durum yönetimi ve sayfa yerleşimi
  types.ts                MediaInfo, MediaFormat, DownloadState tipleri
  index.css               tasarım token'ları (tek renk kaynağı)
  lib/
    api.ts                backend çağrıları, üç katmanlı indirme
    format.ts             bayt, süre, dosya adı biçimlendirme
  hooks/
    useTheme.ts           açık/koyu tema, localStorage'da hatırlanır
    useClipboardPaste.ts  panodan yapıştırma
  components/
    Logo.tsx  Header.tsx  ThemeToggle.tsx  UrlInput.tsx
    EmptyState.tsx  LoadingState.tsx  FetchError.tsx  SourceCards.tsx
    MediaPreview.tsx  FormatTabs.tsx  QualityList.tsx  OptionToggles.tsx
    DownloadButton.tsx  DownloadStatus.tsx  Footer.tsx  Icons.tsx
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

Kaydırma durumu (1920×925'te ölçüldü): boş ekran, yükleniyor iskeleti, hata kutusu,
4 kalite seçenekli video (360p–1080p), MP3 sekmesi ve indirme sırasındaki ilerleme
paneli dahil hiçbir durumda kaydırma yok. Backend 360p altını, üstünde seçenek
varsa listelemiyor (`MIN_HEIGHT`); liste en fazla 4 satır.

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

## Erişilebilirlik notları

- Kalite listesi gerçek `radio` girdileriyle yazıldı, klavyeyle gezilebilir.
- Tüm dokunma hedefleri en az 44 px.
- Yalnızca ikon içeren butonlarda `aria-label` var.
- Tema `color-scheme` ile birlikte değişir, form denetimleri de uyum sağlar.
