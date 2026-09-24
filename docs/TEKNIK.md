# Teknik belgeler

Asil Personal-Converter'ın nasıl çalıştığı, neden böyle tasarlandığı ve nasıl
ayarlanacağı. Kurulum ve kullanım için [README](../README.md)'ye bak.

- [Ayarlar (.env)](#ayarlar-env)
- [API](#api)
- [Backend nasıl çalışıyor](#backend-nasıl-çalışıyor)
- [Frontend: indirme ve ilerleme](#frontend-indirme-ve-ilerleme)
- [Sunucuya taşırken](#sunucuya-taşırken)
- [Frontend klasör yapısı](#frontend-klasör-yapısı)
- [Ekran yüksekliğine uyum](#ekran-yüksekliğine-uyum)
- [Renkleri değiştirmek](#renkleri-değiştirmek)
- [Erişilebilirlik notları](#erişilebilirlik-notları)

## Ayarlar (.env)

Hepsi isteğe bağlı. `backend/.env.example` dosyasını `backend/.env` olarak
kopyalayıp değiştirmek istediğin satırları aç. Geçersiz bir değer (sayı değil, sınır
dışı; ör. `MIN_DOWNLOAD_KBPS=0`, `MP3_BITRATE_KBPS=500`) sunucuyu açılışta anlaşılır
bir mesajla durdurur; çalışırken hataya yol açmaz.

| Değişken | Varsayılan | |
|---|---|---|
| `ALLOWED_HOSTS` | youtube.com, youtu.be, m.youtube.com, music.youtube.com, instagram.com | www. alt alan adları otomatik |
| `MAX_HEIGHT` / `MIN_HEIGHT` | 1080 / 360 | kısa kenara göre |
| `MAX_DURATION_MINUTES` | 90 | |
| `MAX_MEGABYTES` | 2048 | ön kontrol + akış sırasında bayt sayacı |
| `DOWNLOAD_TIMEOUT_MINUTES` | 15 | indirme için en kısa üst süre; büyük dosyada uzar |
| `MIN_DOWNLOAD_KBPS` | 256 | üst süre = boyut ÷ bu hız (en az `DOWNLOAD_TIMEOUT_MINUTES`) |
| `DOWNLOAD_STALL_SECONDS` | 120 | bu süre tek bayt akmazsa indirme kesilir |
| `MAX_CONCURRENT_DOWNLOADS` | 3 | dolu → 503, kuyruk yok |
| `MAX_CONCURRENT_INFO` | 2 | link çözümleme CPU yiyor, ayrı sınır |
| `MAX_DOWNLOADS_PER_IP` | 1 | 0 = sınırsız (test için); IPv6'da /64 bloğu başına |
| `MAX_INFO_PER_IP` / `INFO_PER_MINUTE_PER_IP` | 1 / 20 | yeni link çözümleme (önbellek ıskası) için IP başına |
| `RESERVATION_TTL_SECONDS` | 30 | ayrılıp indirilmeyen yer bu sürede boşalır |
| `CACHE_TTL_MINUTES` / `CACHE_MAX_ENTRIES` | 25 / 200 | video kimliği bazında |
| `THUMBNAIL_CACHE_MEGABYTES` | 32 | kapak görselleri, bellekte |
| `PLAYLIST_LIMIT` | 10 | carousel gönderide çözümlenecek en fazla girdi |
| `MP3_BITRATE_KBPS` | 192 | sabit bit hızı (CBR) |
| `INSTAGRAM_COOKIES` | `./cookies.txt` | göreli yol `backend/`'e göre |
| `FFMPEG_PATH` / `FFPROBE_PATH` | ffmpeg / ffprobe | PATH'te değilse tam yol |
| `HOST` / `PORT` | 127.0.0.1 / 8000 | `serve.py` için |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1,::1` | `X-Forwarded-For`'una güvenilen proxy'ler (`serve.py`) |
| `SHUTDOWN_TIMEOUT_SECONDS` | 20 | kapanırken süren indirmeler en fazla bu kadar beklenir (`serve.py`) |


## API

| | |
|---|---|
| `GET /api/info?url=` | başlık, kanal, süre, kapak ve hazır format listesi (`mp3`, `v360` … `v1080`) |
| `POST /api/download/prepare` | gövde `{url, format, cover?, tags?}` → yer ayırır, ffmpeg'i başlatır; `{ticket, filename, estimatedBytes, expiresIn}` |
| `GET /api/download?ticket=` | bileti tüketir, dosyayı akıtır |
| `DELETE /api/download/{ticket}` | kullanılmayacak bileti hemen bırakır |
| `GET /api/thumbnail?url=[&download=1]` | kapak görseli (Instagram CDN'i başka origin'e görsel vermediği için backend üzerinden) |
| `GET /api/health` | `{"ok": true, "ytDlp": "...", "jsRuntime": "deno"}` |

Hatalar `{"detail": "Türkçe mesaj"}` biçiminde döner; teknik ayrıntı yalnızca konsola loglanır.
`/api/download` bilerek `Content-Length` göndermez (tahmin saparsa indirme bozulur);
tahmini boyut `X-Estimated-Bytes` başlığında, `estimateExact` ise tahminin kaynağın
bildirdiği dosya boyutundan mı (yüzde güvenilir) yoksa bit hızı × süreden mi geldiğini söyler.

**Neden iki adım?** Tarayıcının kendi indiricisine devredilen bir dosyada sunucu
hata dönerse (yoğunluk, IP sınırı) kullanıcı bunu göremez; tarayıcı hata metnini
`.mp4` adıyla kaydedebilir. `prepare` her hatayı dosya indirmesi başlamadan JSON
olarak döndürür. Bilet 30 sn geçerli, onu alan IP'ye bağlı ve tek kullanımlık.

Biletsiz, tek adımlı bir indirme adresi bilerek yok: öyle bir adres başka sitelerden
düz bir bağlantıyla kullanılabilir ve sunucunun bant genişliği onların indirme
butonuna dönüşür. Bilet almak JSON gövdeli bir POST gerektirir; tarayıcı bunu
başka bir origin'den CORS izni olmadan göndermez (bu backend CORS açmaz).

**Yalnızca kendi arayüzünden.** CORS başka sitelerin yanıtı *okumasını* engeller,
isteğin *gönderilmesini* engellemez: başka bir sayfaya konan
`<img src=".../api/info?url=...">` o sayfanın her ziyaretçisinde bir yt-dlp çözümlemesi
başlatırdı. Bu yüzden tarayıcının koyduğu `Sec-Fetch-Site` başlığı `same-origin`
(kendi arayüzü) ya da `none` (adres çubuğu) değilse her `/api` isteği 403 ile reddedilir
(`SameOriginOnly`, `app.py`). Başlığı sayfanın JavaScript'i değiştiremez. Başlık yoksa
(curl, eski tarayıcı) istek geçer; tarayıcı dışı istemcilere karşı koruma IP sınırlarıdır.
Sitenin başka bir sayfaya iframe ile gömülmesi ise sayfayı sunan tarafın işidir
(bkz. [Sunucuya taşırken](#sunucuya-taşırken)).

Bağlantı doğrulanınca parametresiz hâline çevrilir (`watch?v=ID`, `instagram.com/p/KOD/`).
`?si=` ve `?igsh=` paylaşan kişiyi tanımlayan izlerdir; önbellekteki kayıt aynı videoyu
açan herkese döndüğü için kullanıcının yapıştırdığı adres hiçbir yere taşınmaz.
Instagram'ın `instagram.com/share/reel/KOD` kısa bağlantılarındaki kod gönderinin kimliği
değildir; `/api/info` asıl adresi Instagram'ın yönlendirmesinden (tek bir `HEAD`, 302)
öğrenir ve onunla devam eder.

Yalnızca tek bir içeriğe işaret eden bağlantılar kabul edilir. Oynatma listesi,
kanal ve Instagram profili bağlantıları yt-dlp'ye verilmeden reddedilir: yt-dlp
listedeki her videoyu tek tek çözümler (ölçülen: video başına ~1,75 sn) ve yüzlerce
videoluk bir liste dakikalarca bir çözümleme slotunu tutar.

## Backend nasıl çalışıyor

```
backend/
  app.py         FastAPI uçları, link çözümleme sınırları
  serve.py       .env ile başlatma, tek worker
  config.py      .env ayarları
  downloads.py   indirme yaşam döngüsü: rezervasyon → akış → serbest bırakma
  media.py       yt-dlp çözümleme, format seçimi, önbellek, Türkçe hata mesajları
  stream.py      ffmpeg komutu, süreç yönetimi, kesinti tespiti
  relay.py       YouTube akışlarını parça parça okuyan loopback köprü
  thumbnails.py  kapak görselleri, bellek içi önbellek
  tags.py        MP3 ID3 etiketi (başlık, sanatçı, kapak) — bellekte
  limits.py      slot sayaçları, hız sınırı
  names.py       dosya adı temizliği, RFC 5987 Content-Disposition
```

**Format seçimi.** Video çözünürlüğü `min(genişlik, yükseklik)` ile belirlenir —
dikey bir Shorts'ta 1080p = 1080×1920. Aynı çözünürlükte H.264 (avc1) tercih
edilir; bazı telefonlar AV1'i açamıyor. Video ve ses ayrıysa ffmpeg iki girdiyi
`-c copy` ile birleştirir, **yeniden kodlama yok.** Çıktı parçalı mp4
(`frag_keyframe+empty_moov+default_base_moof`), çünkü normal mp4 başına yazılacak
`moov` için dosyanın sonunu bekler. MP3 tek seçenek: en iyi ses akışı
`libmp3lame -b:a 192k` (sabit bit hızı). DRM'li ("maybe" işaretli dahil) ve YouTube'un
yapay zekâyla büyüttüğü (`-sr`) formatlar hiç listelenmez; yt-dlp'nin "possibly damaged"
diye işaretlediği formatlar başka seçenek varsa seçilmez. YouTube reklamlı videolarda
akışı reklam süresi dolmadan vermiyor; yt-dlp bu anı (`available_at`) format bilgisine
yazıyor, `prepare` gerekirse o ana kadar (en fazla 60 sn) bekler.

> **Neden VBR (`-q:a 2`) değil?** VBR MP3'te süre ve konum bilgisi dosyanın
> başındaki Xing başlığında durur; ffmpeg onu dosya bitince geri dönüp yazar.
> Akışa (pipe) yazarken geri dönülemez, başlık boş kalır ve oynatıcılar süreyi
> yanlış gösterir, ileri sarma kayar. CBR'de süre bit hızından tam hesaplanır
> (ölçülen: 634,67 sn, video 634,57 sn). Kaynak ~130 kbps opus/AAC olduğu için
> 192 kbps kalite kaybettirmez; boyut VBR ~190 ile neredeyse aynı.

**Neden `asyncio.create_subprocess_exec` değil?** Windows'ta uvicorn (özellikle
`--reload` ile) SelectorEventLoop kullanır ve asyncio'nun alt süreç API'si orada
`NotImplementedError` fırlatır. Bu yüzden `subprocess.Popen` kullanılıyor; bloklayan
stdout okumaları thread havuzunda yapılıyor, event loop bloklanmıyor. Aynı kod
Linux'ta değişmeden çalışır. `--reload` altında test edildi.

**Relay (YouTube hızı).** YouTube, bir akışı tek uzun istekle okuyanı ilk ~10 MB'tan
sonra gerçek zamana yakın hıza düşürüyor (ölçülen: 0,2–0,3 MB/s). yt-dlp bu yüzden
10 MB'lık `range` parçalarıyla indiriyor ama ffmpeg bunu yapamıyor. Çözüm:
ffmpeg'e CDN adresi yerine `http://127.0.0.1:<rastgele port>/<token>` veriliyor.
Orada uygulamadan bağımsız küçük bir HTTP sunucusu dinliyor ve CDN'den parçaları
sırayla çekip ffmpeg'e tek akış olarak geçiriyor. Tamamen bellekte, adlandırılmış
pipe gerektirmiyor, Windows ve Linux'ta aynı. Sonuç: hat hızında indirme ve bayt
bayt doğru boyut tahmini. Her worker kendi relay'ini açar (token'ı kaydeden süreç ile
ffmpeg'in bağlandığı süreç hep aynıdır), uvicorn unix socket'te dinlese de çalışır,
yalnızca 127.0.0.1'e bağlı olduğu için dışarıdan hiçbir yolla erişilemez. CDN bir
parçanın ortasında 10 sn susarsa parça kaldığı yerden yeniden istenir (en fazla 3
deneme); bu süre ffmpeg'in relay girdisindeki 30 sn'lik zaman aşımından kısa olmak
zorunda, yoksa yeniden deneme hiç devreye giremez (ölçüldü). Relay gövdenin nerede
bittiğini ffmpeg'e her zaman söyler: boyut biliniyorsa `Content-Length`, bilinmiyorsa
`Transfer-Encoding: chunked`. İkisi de olmayınca ffmpeg bağlantının kapanmasını hata
sayıyor ve boyutu bildirilmeyen formatlar (YouTube'un birleşik 360p'si, itag 18) eksiksiz
inse bile %100'de "yarıda kesildi" oluyordu.

**Bütünlük.** ffmpeg yarıda kesilen bir http girdisini "partial file" uyarısıyla
geçip **çıkış kodu 0** ile bitirebiliyor (ölçüldü). Bu yüzden iki kontrol var:
relay her girdinin son baytına kadar teslim edildiğini kaydeder; ffmpeg'in
stderr'indeki kesinti hataları da hata sayılır. İkisinden biri tutarsa akış
temiz kapatılmaz, tarayıcı dosyayı eksik görür ve arayüz "İndirme yarıda kesildi"
der. HLS (m3u8) girdilerinde ffmpeg açılamayan bir parçayı yalnızca uyarıyla atlayıp
0 ile çıkıyor (ölçüldü: ortadan ya da sondan birkaç saniye eksik dosya "tamam"). Bu
yüzden parça 3 kez yeniden denenir (`-seg_max_retry`), yine açılmazsa "failed too many
times" uyarısı kesinti sayılır. ffmpeg `-loglevel level+warning` ile çalışır; kesinti
mesajları yalnızca `[error]` satırlarında aranır, yeniden bağlanma uyarıları hata sayılmaz. CDN'den doğrudan okunan girdilerde ffmpeg en fazla 5 kez yeniden bağlanır ve
30 sn veri gelmezse vazgeçer; ölü bir kaynak indirmeyi asılı tutmaz.

**Süre sınırları.** Sabit bir süre yavaş bağlantıda büyük dosyayı yarıda keserdi
(1 GB'lık dosya 15 dakikada ancak 1,1 MB/sn ile iner). Bu yüzden iki kural var: üst
süre dosya boyutuyla uzar (boyut ÷ 256 KB/sn, en az 15 dk; 1 GB ≈ 68 dk) ve
120 sn boyunca tek bayt akmazsa indirme kesilir. Bu iki yönde de geçerli: kaynak
durursa ffmpeg öldürülür; istemci bağlantıyı açık tutup okumayı bırakırsa (disk dolu,
takılan sekme) tek bir parça 120 sn gönderilemediğinde bağlantı bırakılır. İlerleyen
bir indirme yalnızca üst süreye takılır; takılan ya da okunmayan bir indirme yer tutmaz.
Bağlantı çözümlemede bekleme 90 sn ile sınırlı: yt-dlp'nin Deno çağrısının kendi zaman
aşımı yok. Kullanıcı 90 sn sonra "zamanında alınamadı" görür; çözümleme slotu ise thread
gerçekten bitene kadar dolu kalır. Takılan bir thread durdurulamıyor; slot erken
boşaltılsaydı takılan her çözümleme bir thread ve bir Deno süreci bırakıp yenisine yer
açar, bellek sınırsız dolardı. Çözümleme isteği yapanın değil ayrı bir görevin işidir:
istek iptal edilse de aynı videoyu bekleyen diğer istekler etkilenmez.

**MP3 etiketleri.** ffmpeg pipe'a yazarken ID3 etiketinin boyut alanını dolduramıyor
(sona gelip geri dönmesi gerekir), boyut 0 kalınca oynatıcılar kapağı ve başlığı
görmüyor. Bu yüzden ffmpeg etiketsiz ham MP3 üretiyor ve ID3v2.3 etiketi `mutagen` ile
bellekte oluşturulup akışın başına ekleniyor. WebP kapaklar bellekte JPEG'e çevriliyor.

**Bayat CDN adresleri.** Video bilgisi 25 dakika önbellekte tutulur, ama YouTube
adresleri bazen süresi dolmadan 403 dönmeye başlıyor (gözlendi). ffmpeg kaynağı
açamazsa video önbellekten atılır, taze çözümlenir ve indirme bir kez yeniden denenir;
kullanıcı yalnızca birkaç saniye fazla bekler. İstenen akış kaynakta hiç yoksa
(Instagram sesi olmayan videonun ses bilgisini vermiyor, MP3 seçeneği bu yüzden
görünür) yeniden denenmez; ffmpeg'in "matches no streams" hatası "Bu videoda ses yok"
olarak döner.

**Kapak görselleri.** yt-dlp'nin verdiği kapak adresleri doğrulanmamıştır; en öncelikli
aday (ör. `maxresdefault.webp`) birçok videoda 404 döner. En iyiden kötüye en fazla 6
aday sırayla denenir, ilk sağlam olan bellekte önbelleğe alınır. Büyük kapaklar yalnızca
yeterince yüksek çözünürlükte yüklenmiş videolarda var; eski ve düşük çözünürlüklü
videolarda ilk 6 adayın hepsi 404 döner. YouTube'da bu yüzden her videoda bulunan
`hqdefault.jpg` (480×360) her zaman son yedek olarak denenir. Kapaklar bu sitenin
adresinden sunulduğu için yalnızca jpeg, png, webp, avif ve gif kabul edilir (SVG gibi
betik taşıyabilen türler hiç), yanıt `X-Content-Type-Options: nosniff` ile gider.

**Sınırlar.** Canlı yayınlar reddedilir (sonu olmayan akış slotu sonsuza kadar kilitler).
Boyut sınırı hem tahminle (tahmin yaklaşıksa 1,5× toleransla) hem akış sırasında gerçek
bayt sayacıyla kontrol edilir; sayaç aşılırsa ffmpeg öldürülür. İstemci bağlantıyı
koparırsa (sekme kapandı, iptal) ffmpeg öldürülür ve relay durur. Aynı videoya aynı anda
gelen çözümleme istekleri tek bir yt-dlp çağrısında birleştirilir.

**Kaynakların tek sahibi.** Bir indirmenin slotları, ffmpeg süreci ve relay biletleri
tek bir `Reservation` nesnesine aittir; `release()` kaç kez çağrılırsa çağrılsın bir kez
çalışır. Üç güvence var: akış gövdesinin `finally`'si, yanıt nesnesinin `finally`'si
(istemci gövde başlamadan koparsa gövdeninki hiç çalışmaz) ve kullanılmayan biletler için
30 sn'lik zamanlayıcı. İstemci `prepare` beklerken vazgeçerse yer hemen boşaltılır.

## Frontend: indirme ve ilerleme

İndirme üç katmanlı, sırayla (`src/lib/api.ts`). Üçü de önce `prepare` ile yer ayırtır;
her hata dosya indirilmeye başlamadan arayüzde gösterilir.

1. **`showSaveFilePicker` varsa** (Chrome, Edge): konum sorulur, akış doğrudan
   dosyaya yazılır, RAM'de birikmez. Picker tıklamadan hemen sonra, herhangi bir
   `await`'ten önce açılır; iptal edilirse sessizce çıkılır. Picker dosyayı seçildiği
   anda oluşturduğu için sonraki her hata ya da iptalde dosya silinir; geride boş
   veya yarım dosya kalmaz. Dosya sunucuda yer ayrılmadan yazmaya açılır; diske
   yazılamazsa (disk dolu) akış hemen kapatılır, yer boşalır ve arayüz "Dosya
   kaydedilemedi" der. Pencere hiç açılamazsa (iframe, kurumsal politika) 2. ve 3.
   katmana geçilir.
2. **Yoksa ve dosya Blob sınırının altındaysa** (Brave varsayılanda, Firefox, Safari,
   Android Chrome): akış okunur, ilerleme gösterilir, parçalar Blob'da toplanıp
   kaydedilir. Sınır cihaza göre: `navigator.deviceMemory` varsa GB × 32 MB
   (64–250 MB arası; 4 GB'lık telefonda 128 MB), yoksa dokunmatik cihazda 100 MB,
   masaüstünde 250 MB.
3. **Diğer durumlarda:** tarayıcının kendi indiricisine devredilir; arayüz
   "İndirme tarayıcıya devredildi" yazar.

Yüzde yalnızca boyut kesin biliniyorsa (`estimateExact`) gösterilir ve akış bitene
kadar %99'da sabitlenir. Tahmin yaklaşıksa (HLS'te tepe bit hızı, Instagram) yüzde
yanıltıcı olur; çubuk belirsiz modda kayar, inen MB ve tahmini boyut yazılır. Sunucu
200 döndükten sonra akış kesilirse indirme başarısız sayılır — yarım dosya başarılı
gösterilmez. İptal edilen ya da kullanılmayan bilet sunucuda hemen bırakılır.

İndirme sürerken yeni bağlantı getirilemez ve sayfa temizlenemez (yanlışlıkla inen
dosyayı iptal etmesin); çift tıklama tek istek gönderir.

## Sunucuya taşırken

Bu aşamada deploy dosyası yok; taşırken bilinmesi gerekenler:

- **ffmpeg 7.1 veya üstü.** Doğrudan okunan girdilere (Instagram'ın tamamı) verilen
  `-reconnect_max_retries` 7.1'de geldi; daha eski bir ffmpeg bu seçeneği görünce hiç
  başlamaz. Ubuntu 24.04'ün paketi 6.1, ffmpeg.org'daki Linux derlemeleri güncel.
- **iframe'e gömülme.** `/api` başka sitelerden kullanılamaz (bkz. [API](#api)), ama
  sayfanın kendisi başka bir siteye iframe ile gömülürse içindeki istekler yine
  `same-origin` olur. Sayfayı sunan tarafta `Content-Security-Policy: frame-ancestors 'self'`
  başlığı olmalı.
- **Tek süreç.** Önbellek, IP sınırları, indirme biletleri ve relay bellekte, süreç
  içinde. `uvicorn --workers 4` ile `prepare` bir sürece, `download` başka bir sürece
  düşer ve bilet bulunamaz. `serve.py` bu yüzden `workers=1` ile başlatır. Tek süreç
  yeterli: iş asenkron, ağır kısımlar (yt-dlp, ffmpeg) thread'lerde ve ayrı süreçlerde.
  Daha fazla kapasite gerekirse birden çok örnek çalıştırıp nginx'te `ip_hash`
  kullan; her istemci hep aynı örneğe gider, bilet ve sınırlar tutarlı kalır.
- **Gerçek istemci IP'si.** nginx aynı makinedeyse varsayılan `FORWARDED_ALLOW_IPS`
  (`127.0.0.1,::1`) yeterli; nginx'te `proxy_set_header X-Forwarded-For
  $proxy_add_x_forwarded_for;` olmalı. Başka bir makinedeyse onun adresini yaz. Bu
  listede olmayan bir adresten gelen `X-Forwarded-For` yok sayılır (sahte IP ile
  sınır atlatılamaz). Backend'i proxy'siz doğrudan internete açma.
- **YouTube veri merkezi IP'lerini sık engelliyor.** VDS'lerde "Sign in to confirm
  you're not a bot" hatası yaygın; uygulama bunu "YouTube istekleri geçici olarak
  engelledi" diye gösterir. Kodla çözülebilecek bir şey değil. Seçenekler: konut
  IP'li bir sunucu/proxy, yt-dlp'nin PO token eklentileri ya da çöp bir hesabın
  YouTube çerezleri (hesap kapanabilir). Taşımadan önce hedef sunucuda
  `/api/info` ile birkaç video denemek gerekir.

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
