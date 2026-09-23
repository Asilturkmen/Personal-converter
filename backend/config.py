"""Tüm ayarlar .env üzerinden gelir; burada yalnızca varsayılanlar durur."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f'{name} bir tam sayı olmalı, gelen değer: {raw!r}')


def _list(name: str, default: str) -> list[str]:
    return [item.strip().lower() for item in os.getenv(name, default).split(',') if item.strip()]


# Bu liste olmadan servis herkese açık bir proxy'ye dönüşür. www. alt alan
# adları otomatik olarak kabul edilir.
ALLOWED_HOSTS = frozenset(
    host
    for base in _list('ALLOWED_HOSTS', 'youtube.com,youtu.be,m.youtube.com,music.youtube.com,instagram.com')
    for host in (base, 'www.' + base)
)

MAX_HEIGHT = _int('MAX_HEIGHT', 1080)
# Bunun altındaki çözünürlükler, üstünde seçenek varsa listelenmez.
MIN_HEIGHT = _int('MIN_HEIGHT', 360)
MAX_DURATION_SECONDS = _int('MAX_DURATION_MINUTES', 90) * 60
MAX_BYTES = _int('MAX_MEGABYTES', 2048) * 1024 * 1024
DOWNLOAD_TIMEOUT_SECONDS = _int('DOWNLOAD_TIMEOUT_MINUTES', 15) * 60

MAX_CONCURRENT_DOWNLOADS = _int('MAX_CONCURRENT_DOWNLOADS', 3)
MAX_CONCURRENT_INFO = _int('MAX_CONCURRENT_INFO', 2)
# 0 = sınırsız (yük testi için geçici olarak kapatmak istersen).
MAX_DOWNLOADS_PER_IP = _int('MAX_DOWNLOADS_PER_IP', 1)

CACHE_TTL_SECONDS = _int('CACHE_TTL_MINUTES', 25) * 60
CACHE_MAX_ENTRIES = _int('CACHE_MAX_ENTRIES', 200)

# Göreli yol backend/ klasörüne göre çözülür; uvicorn nereden başlatılırsa
# başlatılsın aynı dosyayı bulur.
_cookies = Path(os.getenv('INSTAGRAM_COOKIES', './cookies.txt'))
INSTAGRAM_COOKIES = _cookies if _cookies.is_absolute() else (BASE_DIR / _cookies).resolve()

FFMPEG_PATH = os.getenv('FFMPEG_PATH', 'ffmpeg')
FFPROBE_PATH = os.getenv('FFPROBE_PATH', 'ffprobe')
