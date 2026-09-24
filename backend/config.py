"""Tüm ayarlar .env üzerinden gelir; burada yalnızca varsayılanlar durur."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def _int(name: str, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    """Hatalı bir değer sunucuyu açılışta durdurur; çalışırken çökertmesin
    (ör. MIN_DOWNLOAD_KBPS=0 her indirmede sıfıra bölerdi)."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        raise SystemExit(f'{name} bir tam sayı olmalı, gelen değer: {raw!r}')
    if value < minimum or (maximum is not None and value > maximum):
        bounds = f'{minimum}–{maximum}' if maximum is not None else f'en az {minimum}'
        raise SystemExit(f'{name} {bounds} olmalı, gelen değer: {value}')
    return value


def _list(name: str, default: str) -> list[str]:
    return [item.strip().lower() for item in os.getenv(name, default).split(',') if item.strip()]


# Bu liste olmadan servis herkese açık bir proxy'ye dönüşür. www. alt alan
# adları otomatik olarak kabul edilir.
ALLOWED_HOSTS = frozenset(
    host
    for base in _list('ALLOWED_HOSTS', 'youtube.com,youtu.be,m.youtube.com,music.youtube.com,instagram.com')
    for host in (base, 'www.' + base)
)

MAX_HEIGHT = _int('MAX_HEIGHT', 1080, minimum=144)
# Bunun altındaki çözünürlükler, üstünde seçenek varsa listelenmez.
MIN_HEIGHT = _int('MIN_HEIGHT', 360, minimum=0)
MAX_DURATION_SECONDS = _int('MAX_DURATION_MINUTES', 90) * 60
MAX_BYTES = _int('MAX_MEGABYTES', 2048) * 1024 * 1024
# İndirme süresi iki kuralla sınırlı (bkz. stream.py):
#  - üst süre: en az DOWNLOAD_TIMEOUT_MINUTES, büyük dosyada MIN_DOWNLOAD_KBPS
#    hızla inmesine yetecek kadar uzar; yavaş bağlantıda dosya yarıda kesilmez.
#  - durma: DOWNLOAD_STALL_SECONDS boyunca tek bayt akmazsa kesilir; takılan
#    ya da okunmayan bir indirme yer tutmaz.
DOWNLOAD_TIMEOUT_SECONDS = _int('DOWNLOAD_TIMEOUT_MINUTES', 15) * 60
MIN_DOWNLOAD_BYTES_PER_SECOND = _int('MIN_DOWNLOAD_KBPS', 256) * 1024
# Bekçi 5 sn'de bir bakıyor; daha kısası anlamsız ve yavaş bir ağda indirmeyi keser.
DOWNLOAD_STALL_SECONDS = _int('DOWNLOAD_STALL_SECONDS', 120, minimum=10)

MAX_CONCURRENT_DOWNLOADS = _int('MAX_CONCURRENT_DOWNLOADS', 3)
MAX_CONCURRENT_INFO = _int('MAX_CONCURRENT_INFO', 2)
# 0 = sınırsız (yük testi için geçici olarak kapatmak istersen).
MAX_DOWNLOADS_PER_IP = _int('MAX_DOWNLOADS_PER_IP', 1, minimum=0)
# Link çözümleme (önbellekte olmayanlar) için IP başına sınırlar. Bunlar
# olmadan tek kişi iki info slotunu sürekli dolu tutup herkese 503 yaşatabilir.
# İkisinde de 0 = sınırsız.
MAX_INFO_PER_IP = _int('MAX_INFO_PER_IP', 1, minimum=0)
INFO_PER_MINUTE_PER_IP = _int('INFO_PER_MINUTE_PER_IP', 20, minimum=0)

# /api/download/prepare ile ayrılan ama indirilmeyen yer bu süre sonunda boşalır.
RESERVATION_TTL_SECONDS = _int('RESERVATION_TTL_SECONDS', 30)
# Bilet beklerken ffmpeg'i kimse okumaz ve durma sayacı işler; bilet süresi
# dolmadan indirme "durdu" diye kesilmesin.
if DOWNLOAD_STALL_SECONDS <= RESERVATION_TTL_SECONDS:
    raise SystemExit(f'DOWNLOAD_STALL_SECONDS ({DOWNLOAD_STALL_SECONDS}), '
                     f'RESERVATION_TTL_SECONDS\'tan ({RESERVATION_TTL_SECONDS}) büyük olmalı')

CACHE_TTL_SECONDS = _int('CACHE_TTL_MINUTES', 25) * 60
CACHE_MAX_ENTRIES = _int('CACHE_MAX_ENTRIES', 200)
THUMBNAIL_CACHE_MEGABYTES = _int('THUMBNAIL_CACHE_MEGABYTES', 32, minimum=0)

# Carousel gönderilerde yt-dlp'nin çözümleyeceği en fazla girdi.
PLAYLIST_LIMIT = _int('PLAYLIST_LIMIT', 10)

# Sabit bit hızı: akışla üretilen MP3'e VBR süre başlığı (Xing) yazılamıyor,
# CBR'de ise oynatıcılar süreyi ve konumu bit hızından doğru hesaplar.
MP3_BITRATE_KBPS = _int('MP3_BITRATE_KBPS', 192, minimum=32, maximum=320)

# --- Sunucu (serve.py) ---------------------------------------------------
HOST = os.getenv('HOST', '127.0.0.1')
PORT = _int('PORT', 8000, maximum=65535)
# X-Forwarded-For'a yalnızca bu adreslerden (reverse proxy) gelen isteklerde
# güvenilir; uvicorn'un kendi ProxyHeadersMiddleware'i uygular (zinciri sağdan
# sola yürür, CIDR destekler). Varsayılan uvicorn'unkiyle aynı: yalnızca
# localhost. nginx başka bir makinedeyse onun adresi yazılmalı.
FORWARDED_ALLOW_IPS = os.getenv('FORWARDED_ALLOW_IPS', '127.0.0.1,::1')
# Kapanırken süren indirmelerin bitmesi en fazla bu kadar beklenir. systemd'nin
# TimeoutStopSec'inden (varsayılan 90 sn) kısa olmalı.
SHUTDOWN_TIMEOUT_SECONDS = _int('SHUTDOWN_TIMEOUT_SECONDS', 20)

# Göreli yol backend/ klasörüne göre çözülür; uvicorn nereden başlatılırsa
# başlatılsın aynı dosyayı bulur.
_cookies = Path(os.getenv('INSTAGRAM_COOKIES', './cookies.txt'))
INSTAGRAM_COOKIES = _cookies if _cookies.is_absolute() else (BASE_DIR / _cookies).resolve()

FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')
FFPROBE_PATH = os.getenv('FFPROBE_PATH', 'ffprobe')
