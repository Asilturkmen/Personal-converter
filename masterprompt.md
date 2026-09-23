# Asil Personal Converter — kurulum ve Claude Code prompt'u

## A. Önce senin yapacakların (Claude Code'dan önce)

PowerShell'i aç ve sırayla çalıştır:

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id Gyan.FFmpeg
winget install -e --id DenoLand.Deno
```

Kurulum bitince **PowerShell'i kapatıp yeniden aç** (PATH güncellensin), sonra
kontrol et:

```powershell
python --version
ffmpeg -version
deno --version
node --version
```

Dördü de bir sürüm numarası yazmalı. Python kurulumunda "Add to PATH" sorulursa
işaretle.

Instagram hikâyeleri için (şimdi değil, backend çalıştıktan sonra):
tarayıcına "Get cookies.txt LOCALLY" eklentisini kur, **çöp bir Instagram
hesabıyla** giriş yap, instagram.com'dayken eklentiyle `cookies.txt` indir,
`backend/` klasörüne koy. Ana hesabını kullanma, bu hesap kapanabilir.

---

## B. Claude Code'a yapıştırılacak prompt

> Buradan aşağısının tamamını kopyala.

Bir video indirme aracının **backend'ini** yazmanı ve mevcut frontend'e
bağlamanı istiyorum.

**Ortam:** Windows, local geliştirme. Sunucuya taşıma (Linux VDS) sonraki aşama,
şimdilik deploy ile ilgili hiçbir şey yazma. Ama yazdığın kod ileride Linux'ta
da değişmeden çalışmalı — platforma özel yol, komut veya API kullanma.

**Kurulu olanlar:** Python 3.12, ffmpeg, Deno, Node (PATH'te). Başlamadan önce
dördünü de kontrol et, eksik varsa bana söyle.

### Projenin değişmez kuralı

Sunucunun diskine **hiçbir zaman** hiçbir dosya yazılmaz. Geçici dosya yok,
temp klasörü yok, kuyruk klasörü yok. Video verisi sunucudan sadece *akarak*
geçer.

### Mevcut durum

- Frontend: **React + TypeScript + Vite**, `localhost:5173`'te çalışıyor
- Sadece boş durum ekranı var: başlık, bağlantı giriş kutusu (Yapıştır + Getir
  butonları), "Henüz bir bağlantı yok" kartı, altta üç bilgi kartı
  (YouTube / Instagram / MP3), tema değiştirme butonu, footer
- Video yüklendikten sonraki ekran **yok** — onu sen tasarlayacaksın (aşağıda)
- Backend yok

Önce mevcut frontend kodunu oku: bileşen yapısını, stil yöntemini (CSS modül,
Tailwind, düz CSS — ne kullanılıyorsa), renk/boşluk/köşe yarıçapı değerlerini,
tema sistemini. Yeni ekleyeceğin her şey bunlarla **birebir aynı dilde**
olmalı. Yeni bir stil kütüphanesi ekleme, mevcut olanı kullan.

### Mimari

```
yt-dlp (metadata + CDN URL'leri)  →  ffmpeg (CDN'den okur, stdout'a yazar)  →  HTTP response
```

- yt-dlp **indirme yapmaz**. `extract_info(url, download=False)` ile sadece
  metadata ve format URL'lerini çıkarır. Python kütüphanesi olarak import
  edilir, subprocess olarak çağrılmaz.
- ffmpeg o URL'leri girdi olarak alır, doğrudan Google/Meta CDN'inden okur ve
  çıktısını `pipe:1`'e basar. Tek süreç, ara tamponlama yok.
- FastAPI bu stdout'u `StreamingResponse` ile istemciye akıtır.

### Teknoloji

- Python 3.12, FastAPI, uvicorn, python-dotenv
- **`yt-dlp[default]`** — `[default]` şart, YouTube imza çözümü için gereken
  `yt-dlp-ejs` bileşenini getiriyor
- **Deno** — yt-dlp bunu varsayılan JS runtime olarak kullanıyor, ek ayar
  gerekmez. Node'u yt-dlp için kullanma (varsayılan olarak kapalı, ayrı
  yapılandırma ister). Uygulama açılışında yt-dlp'nin JS runtime bulup
  bulamadığını kontrol et; bulamazsa "No supported JavaScript runtime" uyarısı
  verir ve formatların çoğu eksik gelir — bu durumda konsola net bir uyarı bas.

Klasör yapısı:

```
proje/
  frontend/        (mevcut Vite projesi)
  backend/
    app.py         (gerekirse modüllere böl)
    requirements.txt
    .env.example
  README.md
```

### API sözleşmesi

Frontend'in format mantığını bilmesi gerekmesin — backend hazır listeyi dönsün.

#### `GET /api/info?url=<url>`

```json
{
  "url": "https://www.youtube.com/watch?v=ABC",
  "source": "youtube",
  "title": "Video başlığı",
  "uploader": "Kanal adı",
  "duration": 634,
  "thumbnail": "https://...",
  "formats": [
    { "id": "mp3",  "label": "MP3",   "kind": "audio", "estimatedBytes": 9600000 },
    { "id": "v360", "label": "360p",  "kind": "video", "height": 360,  "estimatedBytes": 41000000 },
    { "id": "v720", "label": "720p",  "kind": "video", "height": 720,  "estimatedBytes": 118000000 }
  ]
}
```

`estimatedBytes` ilerleme çubuğu için şart. Video formatlarında video + ses
akışlarının `filesize` / `filesize_approx` değerleri toplanır; ikisi de yoksa
`tbr × duration` ile tahmin edilir.

Hatalar `{"detail": "kullanıcıya gösterilecek Türkçe mesaj"}` formatında dönsün.
Teknik hata metnini kullanıcıya olduğu gibi gösterme, konsola logla.

#### `GET /api/download?url=<url>&format=<id>`

Dosyayı akıtır. `format` değeri `/api/info`'nun döndüğü `id` olmalı.

Başlıklar:
- `Content-Disposition` — RFC 5987 ile (Türkçe karakterli başlıklar için şart)
- `Cache-Control: no-store`
- `X-Accel-Buffering: no`
- `X-Estimated-Bytes` — tahmini boyut
- `Access-Control-Expose-Headers` gerekmez (aynı origin), ama `X-Estimated-Bytes`
  frontend'den okunabilmeli

**`Content-Length` GÖNDERME.** Tahmini değer gönderilirse gerçek boyut sapınca
indirme bozulur (fazlaysa tarayıcı donar, azsa dosya yarım iner).

#### `GET /api/health`

`{"ok": true, "ytDlp": "<versiyon>", "jsRuntime": "<bulunan runtime veya null>"}`

### Format seçim kuralları

**Video:**
- Kullanıcının seçtiği yüksekliği geçme, 1080p üst sınır
- **Filtrelemede `min(width, height)` kullan, `height` değil.** Dikey videolarda
  (Shorts, Reels) 1080p video 1080×1920'dir, `height` 1920 olur ve naif filtre
  en iyi kaliteyi eler. Etiketler de kısa kenara göre olsun ("1080p").
- Aynı çözünürlükte birden fazla kodek varsa **avc1/h264 tercih et**. YouTube
  sık sık AV1 servis ediyor, bazı telefon oynatıcıları açamıyor.
- Video ve ses ayrıysa ffmpeg'e iki girdi ver, `-c copy` ile birleştir.
  **Asla yeniden kodlama yapma** — `-vf scale`, `-c:v libx264` gibi şeyler yok.
- Çıktı **parçalı mp4** olmalı:
  `-movflags frag_keyframe+empty_moov+default_base_moof -f mp4`
  Normal mp4 dosyanın başına moov atom yazmak ister, akışa yazılamaz.
- Instagram videoları genelde tek parça (video+ses aynı akışta) — o durumda tek
  girdi, `-c copy`.
- ffmpeg girdilerine yt-dlp'nin format bilgisindeki `http_headers`'ı geçir
  (User-Agent, Referer vb.), yoksa CDN 403 dönebilir. Her girdiye
  `-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5` ekle.

**MP3:** Tek seçenek, kbps seçimi yok. En iyi ses akışını al,
`-vn -c:a libmp3lame -q:a 2 -id3v2_version 3 -f mp3` (VBR, ~190 kbps).
Kaynak ~130 kbps opus olduğu için daha yüksek bitrate kalite katmaz.

### Windows'a özel dikkat

- **`asyncio.create_subprocess_exec` uvicorn altında Windows'ta
  `NotImplementedError` fırlatabilir** (özellikle `--reload` ile, event loop
  Proactor yerine Selector olduğunda). Bunu mutlaka test et. Sorun çıkarsa
  `subprocess.Popen` + ayrı bir thread'de stdout okuma yaklaşımına geç — bu
  hem Windows'ta hem Linux'ta çalışır. Hangi yolu seçtiğini README'de açıkla.
- Dosya adlarında Windows'ta yasak karakterleri temizle: `< > : " / \ | ? *`
  ve kontrol karakterleri. Türkçe karakterleri koru.
- Süreç öldürme: `proc.kill()` her iki platformda çalışır, platforma özel
  sinyal kullanma.

### Güvenlik ve limitler

Hepsi `.env` ile ayarlanabilir olsun, varsayılanlar aşağıda.

**Host beyaz listesi:** Sadece youtube.com, youtu.be, m.youtube.com,
music.youtube.com, instagram.com ve www alt alan adları. Bu olmadan servis açık
proxy'ye dönüşür.

**Canlı yayın reddi:** `info["is_live"]` true ise 422 dön, mesaj: "Canlı
yayınlar desteklenmiyor." Canlı yayının süresi, boyutu ve sonu yoktur; kabul
edilirse slot sonsuza kadar kilitlenir.

**Süre sınırı:** 90 dakika.

**Boyut sınırı:** 2 GB. `estimatedBytes` ile ön kontrol **artı** akış
sırasında bayt sayacı. Sayaç sınırı aşarsa ffmpeg'i öldür. Ön kontrol
tahmindir, tek güvenilir koruma sayaçtır.

**Zaman aşımı:** Bir indirme 15 dakikayı geçerse süreci öldür.

**İki ayrı semaphore:**
- İndirme: 3 eşzamanlı
- **`/api/info` için ayrı: 2 eşzamanlı.** Asıl CPU yükü burada — her link
  çözümlemesi JS runtime'ı çalıştırıp iş başına 0.5–2 saniye tam çekirdek
  harcıyor. İndirme `-c copy` olduğu için CPU kullanmıyor.

**IP başına 1 eşzamanlı indirme.** Yoksa tek kişi (5 sekme açarak) tüm
kapasiteyi kendine ayırır.

**Slot doluysa bekletme, 503 ile anında reddet**, mesaj: "Şu an yoğunluk var,
birkaç saniye sonra tekrar dene." Kuyruk açık soket demek.

**Cache:** Video ID bazında (URL string'i değil — `youtu.be/X`,
`youtube.com/watch?v=X`, `youtube.com/shorts/X` aynı video), 25 dakika TTL,
en fazla 200 kayıt. Format URL'leri ~6 saat geçerli.

**İstemci koparsa ffmpeg'i öldür.** Yoksa kullanıcı sekmeyi kapattığında süreç
arkada çalışmaya devam eder.

### Instagram

`INSTAGRAM_COOKIES` env değişkeniyle bir `cookies.txt` yolu alınsın (varsayılan
`./cookies.txt`, dosya yoksa çerezsiz devam et), yt-dlp'ye `cookiefile` olarak
verilsin. **Çerezleri tarayıcıdan otomatik okuma (`cookiesfrombrowser`)
kullanma** — Windows'ta Chromium tabanlı tarayıcılarda şifreleme yüzünden
güvenilir çalışmıyor.

- Reels ve gönderi videoları çoğunlukla çerezsiz çalışır
- **Hikâyeler çerez olmadan çalışmaz** ve çerez düzenli olarak düşer
- Giriş/çerez kaynaklı hataları özel olarak yakala, mesaj:
  "Instagram oturumu gerekli veya süresi dolmuş — cookies.txt yenilenmeli."
- Carousel gönderilerde yt-dlp playlist döner. Şimdilik ilk **video** girdisini
  al (fotoğrafları atla), koda yorum olarak not düş.

### Frontend: yüklenmiş durum ekranı

"Henüz bir bağlantı yok" kartının yerine, aynı boyutta ve aynı görsel dilde
şunları göster:

- **Yükleniyor durumu:** "Getir"e basınca veya yapıştırınca. İskelet (skeleton)
  ya da sade bir gösterge.
- **Video kartı:** kapak görseli (dikey videolarda dikey oranda göster, kırpma),
  başlık (en fazla 2 satır), kanal/kullanıcı adı, süre.
- **Format seçimi:** `/api/info`'dan gelen listeden butonlar. MP3 ayrı dursun,
  video çözünürlükleri kendi grubunda. Her butonda tahmini boyut küçük yazıyla
  ("~118 MB"). Varsayılan seçili: 720p varsa o, yoksa en yüksek video.
- **İndir butonu:** seçili formata göre metin ("MP3 indir", "720p indir").
- **İlerleme:** yüzde + çubuk + "45 / 118 MB" gibi metin. Bitince "İndirildi"
  onayı, sonra yeni link yapıştırmaya hazır.
- **Hata durumu:** backend'den gelen `detail` mesajını göster, "Tekrar dene"
  butonu. Hata mesajları ne olduğunu ve ne yapılacağını söylesin, özür dilemesin.

Tema değiştirmede (açık/koyu) tüm yeni öğeler doğru görünmeli. Mobilde de
düzgün dizilmeli — site telefondan da kullanılacak.

"Yapıştır" butonu `navigator.clipboard.readText()` kullanıyorsa izin
reddedilirse sessizce başarısız olmasın, kullanıcıya elle yapıştırmasını söyle.

### Frontend: indirme ve ilerleme

**CORS kullanma.** Vite proxy ile çöz:

```ts
// vite.config.ts
server: { proxy: { '/api': 'http://127.0.0.1:8000' } }
```

Yollar geliştirmede ve sunucuda birebir aynı kalır.

İndirme üç katmanlı, sırayla dene:

1. **`window.showSaveFilePicker` varsa:** kullanıcıya konum sordur, `fetch` ile
   akışı oku, baytları sayarak ilerlemeyi göster, doğrudan dosyaya yaz. RAM'de
   birikme yok.
   **Kritik:** `showSaveFilePicker()` kullanıcı tıklamasının hemen ardından,
   **herhangi bir `await`'ten önce** çağrılmalı. Önce `fetch` beklenirse
   tarayıcı "user activation" süresini aşar ve picker açılmaz.
   Kullanıcı picker'ı iptal ederse sessizce çık, hata gösterme.
   TypeScript tipleri eksikse `@types/wicg-file-system-access` ekle.
2. **API yoksa ve `estimatedBytes` < 250 MB ise:** `fetch` ile akışı oku,
   ilerlemeyi göster, parçaları Blob'da topla, bitince `URL.createObjectURL` +
   geçici `<a download>` ile kaydet, sonra `revokeObjectURL`.
   Not: **Brave bu API'yi varsayılan olarak kapatıyor**, Firefox ve Safari'de
   hiç yok — kullanıcıların çoğu bu yola düşecek. Bu yüzden bu katman önemli.
3. **Diğer durumlarda** (250 MB üstü, API yok): gizli `<a href download>` ile
   normal indirme başlat, tarayıcının kendi göstergesi kullanılsın. Arayüzde
   "İndirme tarayıcıya devredildi" yaz. Büyük dosyayı Blob'a alma — telefonda
   belleği patlatır.

Yüzde `X-Estimated-Bytes` ile hesaplanır. Tahmin tutmayabilir: %99'da sabitle,
akış bitince %100'e atla. Gerçek bayt tahmini aşarsa çubuğu geri sarma.

Akış sırasında HTTP 200 dönüp sonra kesilirse (ffmpeg hatası, limit aşımı)
indirmeyi başarısız say ve kullanıcıya söyle — yarım dosyayı başarılı gösterme.

### Yapma

- Diske yazma (geçici dosya dahil)
- Video yeniden kodlama (`-c copy` dışına çıkma)
- `Content-Length` gönderme
- `localStorage`/`sessionStorage` kullanma
- Kuyruk yapısı kurma (dolu = reddet)
- yt-dlp'yi subprocess olarak çağırma
- `cookiesfrombrowser` kullanma
- Yeni UI/stil kütüphanesi ekleme
- Deploy, nginx, systemd, Docker ile ilgili dosya yazma (sonraki aşama)

### README

Windows için kurulum ve çalıştırma adımları:
- venv oluşturma ve etkinleştirme (PowerShell: `.venv\Scripts\Activate.ps1`,
  ExecutionPolicy hatası çıkarsa çözümü)
- `pip install -r requirements.txt`
- backend'i başlatma (`uvicorn app:app --port 8000`)
- frontend'i başlatma (`npm run dev`)
- `.env` değişkenleri
- `cookies.txt` nereye konur
- yt-dlp'yi güncelleme: `pip install -U "yt-dlp[default]"` — YouTube ayda
  birkaç kez bir şeyi kırıyor, indirme bozulursa ilk yapılacak şey bu

### Kabul kriterleri

Bitince bunları kendin test et, sonucu bana raporla:

1. Normal YouTube videosu → MP3 ve 360p/720p/1080p iner, dosyalar oynatılabilir
2. YouTube Shorts (dikey) → **1080p seçeneği listede görünür** ve kapak dikey
   gösterilir
3. Instagram reel → iner
4. Instagram hikâyesi → çerezsiz anlaşılır hata verir (çerezli testi ben
   yapacağım)
5. Canlı yayın linki → "Canlı yayınlar desteklenmiyor" hatası
6. Desteklenmeyen site linki (ör. vimeo) → beyaz liste hatası
7. 4 indirme aynı anda başlatılır (farklı IP simülasyonu gerekirse IP başına
   sınırı geçici kapat) → 3'ü çalışır, 4'ü 503 alır
8. Aynı IP'den 2. eşzamanlı indirme → reddedilir
9. İndirme sırasında sekme kapatılır → ffmpeg süreci ölür. PowerShell'de doğrula:
   `Get-Process ffmpeg -ErrorAction SilentlyContinue` hiçbir şey dönmemeli
10. İndirme sırasında ilerleme yüzdesi artar (Brave'de 2. katman üzerinden)
11. İndirme boyunca proje klasörü ve `$env:TEMP` büyümez
12. Türkçe karakterli başlıklı video → dosya adı bozulmadan iner
13. `/api/health` → `jsRuntime` alanı `deno` gösterir
14. Açık ve koyu temada, masaüstü ve dar (mobil) genişlikte yeni ekran düzgün
    görünür
