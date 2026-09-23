"""yt-dlp ile bağlantı çözümleme ve format seçimi.

yt-dlp burada yalnızca metadata ve CDN adreslerini çıkarır; hiçbir şey
indirmez, diske hiçbir şey yazmaz (cachedir kapalı, çerez dosyası geri
yazılmaz). İndirmenin kendisi ffmpeg'in işi (bkz. stream.py).
"""

from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from urllib.parse import parse_qs, quote, urlsplit

import yt_dlp
from yt_dlp.utils import DownloadError

import config

log = logging.getLogger('converter.media')

# Kısa kenara göre standart etiketler. 1080p üst sınır config.MAX_HEIGHT ile.
LADDER = (144, 240, 360, 480, 720, 1080, 1440, 2160)
MP3_KBPS = 190  # -q:a 2 ortalaması; yalnızca boyut tahmini için


class UserError(Exception):
    """Mesajı olduğu gibi kullanıcıya gösterilebilen hata."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


# --------------------------------------------------------------------------
# Bağlantı doğrulama ve video kimliği
# --------------------------------------------------------------------------

YOUTUBE_PATH_ID = re.compile(r'^/(?:shorts|live|embed|v)/([A-Za-z0-9_-]{11})')
INSTAGRAM_PATH_ID = re.compile(r'^/(?:[^/]+/)?(?:p|reels?|tv)/([A-Za-z0-9_-]+)')
INSTAGRAM_STORY = re.compile(r'^/stories/([^/]+)(?:/(\d+))?')


def validate_url(raw: str) -> str:
    url = (raw or '').strip()
    if not url:
        raise UserError('Bir bağlantı yapıştır.')
    if '://' not in url:
        url = 'https://' + url

    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if parts.scheme not in ('http', 'https') or host not in config.ALLOWED_HOSTS:
        raise UserError('Yalnızca YouTube ve Instagram bağlantıları destekleniyor.')
    return url


def platform_of(url: str) -> str:
    host = (urlsplit(url).hostname or '').lower()
    return 'instagram' if host.endswith('instagram.com') else 'youtube'


def cache_key(url: str) -> str:
    """Aynı videoya giden farklı bağlantılar aynı anahtarı üretir:
    youtu.be/X, youtube.com/watch?v=X ve youtube.com/shorts/X hepsi yt:X."""
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    path = parts.path

    if host.endswith('youtu.be'):
        video_id = path.strip('/').split('/')[0]
        if video_id:
            return 'yt:' + video_id
    elif 'youtube.com' in host:
        video_id = parse_qs(parts.query).get('v', [None])[0]
        if not video_id and (match := YOUTUBE_PATH_ID.match(path)):
            video_id = match.group(1)
        if video_id:
            return 'yt:' + video_id
    elif host.endswith('instagram.com'):
        if match := INSTAGRAM_PATH_ID.match(path):
            return 'ig:' + match.group(1)
        if match := INSTAGRAM_STORY.match(path):
            return 'igs:' + match.group(1) + ':' + (match.group(2) or '')

    return 'url:' + host + path + '?' + parts.query


# --------------------------------------------------------------------------
# Çözümleme sonucu
# --------------------------------------------------------------------------

@dataclass
class Stream:
    """ffmpeg'e verilecek tek bir girdi."""
    url: str
    headers: dict[str, str]
    # HLS'ten gelen AAC, ADTS çerçeveli olur; mp4'e kopyalanırken
    # aac_adtstoasc gerekir.
    hls_aac: bool = False
    # YouTube tek istekte okunan akışı ilk ~10 MB'tan sonra yavaşlatıyor;
    # yt-dlp bu yüzden parça parça (range) indiriyor. Bu alan doluysa akış
    # relay.py üzerinden aynı şekilde parçalı okunur.
    chunk_size: int | None = None
    filesize: int | None = None


@dataclass
class Choice:
    id: str
    label: str
    kind: str  # 'video' | 'audio'
    estimated_bytes: int
    inputs: list[Stream]
    height: int | None = None
    fps: int | None = None
    codec: str | None = None

    def public(self) -> dict:
        data = {'id': self.id, 'label': self.label, 'kind': self.kind, 'estimatedBytes': self.estimated_bytes}
        if self.kind == 'video':
            data.update(height=self.height, fps=self.fps, codec=self.codec)
        return data


@dataclass
class Media:
    url: str
    source: str
    title: str
    uploader: str
    duration: int
    thumbnail: str | None
    thumbnail_headers: dict[str, str]
    width: int | None
    height: int | None
    choices: dict[str, Choice] = field(default_factory=dict)

    def public(self) -> dict:
        return {
            'url': self.url,
            'source': self.source,
            'title': self.title,
            'uploader': self.uploader,
            'duration': self.duration,
            # Meta CDN'i görselleri başka origin'e göstermiyor (CORP); kapak
            # bu yüzden backend üzerinden, bellekte geçirilerek sunuluyor.
            'thumbnail': '/api/thumbnail?url=' + quote(self.url, safe='') if self.thumbnail else None,
            'width': self.width,
            'height': self.height,
            'formats': [choice.public() for choice in self.choices.values()],
        }


# --------------------------------------------------------------------------
# Önbellek: video kimliği bazında, TTL + en fazla N kayıt
# --------------------------------------------------------------------------

class InfoCache:
    def __init__(self, ttl: int, max_entries: int):
        self.ttl = ttl
        self.max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, Media]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> Media | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            stored_at, media = item
            if time.monotonic() - stored_at > self.ttl:
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return media

    def put(self, key: str, media: Media) -> None:
        with self._lock:
            self._items[key] = (time.monotonic(), media)
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)


cache = InfoCache(config.CACHE_TTL_SECONDS, config.CACHE_MAX_ENTRIES)


# --------------------------------------------------------------------------
# yt-dlp
# --------------------------------------------------------------------------

def _ydl_options(platform: str) -> dict:
    options = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'skip_download': True,
        # Disk yasak: yt-dlp'nin imza/önbellek klasörünü kapat.
        'cachedir': False,
        'socket_timeout': 20,
        'logger': _YdlLogger(),
    }
    if platform == 'instagram' and config.INSTAGRAM_COOKIES.is_file():
        options['cookiefile'] = str(config.INSTAGRAM_COOKIES)
    return options


class _YdlLogger:
    """yt-dlp'nin çıktısını kendi log'umuza yönlendirir."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        log.warning('yt-dlp: %s', msg)

    def error(self, msg: str) -> None:
        log.debug('yt-dlp: %s', msg)


def extract(url: str) -> Media:
    """Engelleyen çağrı; thread havuzunda çalıştırılmalı."""
    platform = platform_of(url)
    ydl = yt_dlp.YoutubeDL(_ydl_options(platform))
    try:
        info = ydl.extract_info(url, download=False)
    except DownloadError as error:
        log.info('extract başarısız (%s): %s', url, error)
        raise UserError(_friendly_error(str(error), platform), 422) from None
    finally:
        # close() çerez dosyasını diske geri yazıyor; bunu engelle.
        ydl.params['cookiefile'] = None
        ydl.close()

    if info is None:
        raise UserError('Bu bağlantıda indirilebilir bir video bulunamadı.', 422)

    if info.get('_type') == 'playlist' or info.get('entries') is not None:
        # Carousel gönderiler (ve hikâye listeleri) playlist olarak döner.
        # Şimdilik ilk *video* girdisini alıyoruz; fotoğraflar atlanıyor.
        # İleride kullanıcıya girdi seçtirmek istersek burası değişecek.
        entries = [entry for entry in (info.get('entries') or []) if entry and _has_video(entry)]
        if not entries:
            raise UserError('Bu gönderide video yok; yalnızca fotoğraf içeriyor.', 422)
        info = entries[0]

    if info.get('is_live') or info.get('live_status') in ('is_live', 'is_upcoming'):
        raise UserError('Canlı yayınlar desteklenmiyor.', 422)

    duration = int(info.get('duration') or 0)
    if duration > config.MAX_DURATION_SECONDS:
        limit = config.MAX_DURATION_SECONDS // 60
        raise UserError(f'Video çok uzun. En fazla {limit} dakikalık videolar indirilebilir.', 422)

    return _build_media(url, platform, info, duration)


def _has_video(entry: dict) -> bool:
    return any(_vcodec(f) is not None for f in entry.get('formats') or [entry])


def _friendly_error(text: str, platform: str) -> str:
    lowered = text.lower()

    if platform == 'instagram' and any(
        needle in lowered
        for needle in ('login', 'log in', 'cookie', 'rate-limit', 'rate limit', 'not available', 'authentication')
    ):
        return 'Instagram oturumu gerekli veya süresi dolmuş — cookies.txt yenilenmeli.'
    if 'live event will begin' in lowered or 'premieres in' in lowered:
        return 'Canlı yayınlar desteklenmiyor.'
    if 'live stream recording is not available' in lowered:
        return 'Bu canlı yayının kaydı mevcut değil; yalnızca kaydı yayımlanmış yayınlar indirilebilir.'
    if 'private video' in lowered:
        return 'Bu video gizli. Yalnızca herkese açık videolar indirilebilir.'
    if 'confirm your age' in lowered or 'age-restricted' in lowered:
        return 'Yaş sınırlı videolar indirilemiyor.'
    if 'not a bot' in lowered:
        return 'YouTube istekleri geçici olarak engelledi. Birkaç dakika sonra tekrar dene.'
    if 'members-only' in lowered or 'join this channel' in lowered:
        return 'Bu video yalnızca kanal üyelerine açık, indirilemez.'
    if 'unavailable' in lowered or 'does not exist' in lowered or 'removed' in lowered:
        return 'Video bulunamadı. Kaldırılmış ya da bağlantı hatalı olabilir.'
    return 'Bu bağlantıdaki video alınamadı. Bağlantının doğru ve herkese açık olduğunu kontrol et.'


# --------------------------------------------------------------------------
# Format seçimi
# --------------------------------------------------------------------------

def _vcodec(f: dict) -> str | None:
    """None = video yok. yt-dlp'de 'none' yok demek, None bilinmiyor demek."""
    codec = f.get('vcodec')
    if codec == 'none':
        return None
    if codec is None:
        # Bilinmiyor: çözünürlük bilgisi varsa video var sayılır.
        return 'unknown' if (f.get('height') or f.get('width')) else None
    return codec


def _acodec(f: dict) -> str | None:
    codec = f.get('acodec')
    if codec == 'none':
        return None
    if codec is None:
        # Instagram'ın tek parça akışlarında acodec çoğu zaman bilinmiyor.
        return 'unknown'
    return codec


def _usable(f: dict) -> bool:
    return bool(f.get('url')) and f.get('protocol', 'https') in ('http', 'https', 'm3u8', 'm3u8_native')


def _is_direct(f: dict) -> bool:
    """Tek dosya (https) HLS'e tercih edilir: ffmpeg için daha az istek."""
    return f.get('protocol') in ('https', 'http')


def _size(f: dict, duration: int) -> int:
    size = f.get('filesize') or f.get('filesize_approx')
    if size:
        return int(size)
    tbr = f.get('tbr') or 0
    return int(tbr * 1000 / 8 * duration)


def _bucket(width: int | None, height: int | None) -> int | None:
    """Dikey videoda 1080p = 1080x1920; height değil kısa kenar esas alınır.
    Geniş sinema oranında (1920x800) uzun kenar da hesaba katılır."""
    if not width and not height:
        return None
    short = min(width or height, height or width)
    long = max(width or height, height or width)
    equivalent = max(short, long * 9 / 16)
    return min(LADDER, key=lambda step: abs(step - equivalent))


def _is_avc(codec: str | None) -> bool:
    return bool(codec) and (codec.startswith('avc') or codec.startswith('h264'))


def _stream(f: dict) -> Stream:
    hls = str(f.get('protocol', '')).startswith('m3u8')
    acodec = f.get('acodec')
    return Stream(
        url=f['url'],
        headers=dict(f.get('http_headers') or {}),
        hls_aac=hls and (acodec is None or str(acodec).startswith('mp4a')),
        chunk_size=None if hls else (f.get('downloader_options') or {}).get('http_chunk_size'),
        filesize=f.get('filesize'),
    )


def _short_codec(codec: str | None) -> str | None:
    if not codec or codec == 'unknown':
        return None
    if _is_avc(codec):
        return 'H.264'
    if codec.startswith(('vp9', 'vp09')):
        return 'VP9'
    if codec.startswith('av01'):
        return 'AV1'
    if codec.startswith(('hev', 'hvc', 'h265')):
        return 'H.265'
    return codec.split('.')[0].upper()


def _build_media(url: str, platform: str, info: dict, duration: int) -> Media:
    formats = [f for f in info.get('formats') or [info] if _usable(f)]

    # Sadece-ses için vcodec açıkça 'none' olmalı: Instagram'ın hiçbir bilgisi
    # olmayan tek parça akışları (vcodec/acodec/boyut hepsi None) ses sanılmasın.
    audio_only = [f for f in formats if f.get('vcodec') == 'none' and _acodec(f) is not None]
    videos = [f for f in formats if _vcodec(f) is not None]

    if not duration:
        # Instagram çerezsiz modda süre vermiyor; boyut tahmini ve MP3 için gerekli.
        probe = (audio_only or videos or [None])[0]
        duration = _probe_duration(probe) if probe else 0

    # Video ile birleştirilecek ses: -c copy ile mp4'e girebilmesi için
    # önce AAC (m4a), yoksa en iyi ses.
    # language_preference: çok dilli videolarda orijinal ses izi 10 alır,
    # diğerleri -1; HLS akışlarında hiç yok (None), onları -1 sayıyoruz.
    # DRC (dinamik aralığı sıkıştırılmış) varyantlar geride kalır.
    def lang(f: dict) -> int:
        value = f.get('language_preference')
        return -1 if value is None else value

    def audio_rank(f: dict) -> tuple:
        codec = f.get('acodec') or ''
        return (
            lang(f),
            codec.startswith('mp4a'),
            _is_direct(f),
            'drc' not in str(f.get('format_id')),
            f.get('abr') or f.get('tbr') or 0,
        )

    def best_audio_any(f: dict) -> tuple:
        return (lang(f), _is_direct(f), 'drc' not in str(f.get('format_id')), f.get('abr') or f.get('tbr') or 0)

    pairing_audio = max(audio_only, key=audio_rank) if audio_only else None

    choices: dict[str, Choice] = {}

    # --- MP3: en iyi ses akışı (yoksa en küçük birleşik akış) yeniden kodlanır.
    mp3_source = max(audio_only, key=best_audio_any) if audio_only else None
    if mp3_source is None:
        combined = [f for f in videos if _acodec(f) is not None]
        if combined:
            mp3_source = min(combined, key=lambda f: f.get('tbr') or 0)
    if mp3_source is not None and duration:
        choices['mp3'] = Choice(
            id='mp3',
            label='MP3',
            kind='audio',
            estimated_bytes=int(MP3_KBPS * 1000 / 8 * duration),
            inputs=[_stream(mp3_source)],
        )

    # --- Video: her çözünürlük basamağı için en iyi aday.
    best: dict[int, tuple[tuple, dict]] = {}
    for f in videos:
        bucket = _bucket(f.get('width'), f.get('height'))
        if bucket is None or bucket > config.MAX_HEIGHT:
            continue
        has_audio = _acodec(f) is not None
        if not has_audio and pairing_audio is None:
            continue
        rank = (
            _is_avc(_vcodec(f)),               # telefonlar AV1'i her zaman açamıyor
            _is_direct(f),
            f.get('fps') or 0,
            f.get('tbr') or 0,
        )
        if bucket not in best or rank > best[bucket][0]:
            best[bucket] = (rank, f)

    if any(bucket >= config.MIN_HEIGHT for bucket in best):
        best = {bucket: value for bucket, value in best.items() if bucket >= config.MIN_HEIGHT}

    for bucket in sorted(best):
        f = best[bucket][1]
        if _acodec(f) is not None:
            inputs = [_stream(f)]
            size = _size(f, duration)
        else:
            inputs = [_stream(f), _stream(pairing_audio)]
            size = _size(f, duration) + _size(pairing_audio, duration)

        fps = f.get('fps')
        choices[f'v{bucket}'] = Choice(
            id=f'v{bucket}',
            label=f'{bucket}p',
            kind='video',
            height=bucket,
            estimated_bytes=size,
            inputs=inputs,
            fps=round(fps) if fps else None,
            codec=_short_codec(_vcodec(f)),
        )

    if not choices:
        raise UserError('Bu videonun indirilebilir bir formatı bulunamadı.', 422)

    # Kapak ve oran için en büyük video karesi.
    width = height = None
    if videos:
        biggest = max(videos, key=lambda f: (f.get('width') or 0) * (f.get('height') or 0))
        width, height = biggest.get('width'), biggest.get('height')

    thumbnail, thumbnail_headers = _pick_thumbnail(info)

    return Media(
        url=url,
        source=platform,
        title=_title(info, platform),
        uploader=(info.get('uploader') or info.get('channel') or info.get('uploader_id') or '').strip(),
        duration=duration,
        thumbnail=thumbnail,
        thumbnail_headers=thumbnail_headers,
        width=width,
        height=height,
        choices=choices,
    )


def _title(info: dict, platform: str) -> str:
    title = (info.get('title') or '').strip()
    description = (info.get('description') or '').strip()
    # Instagram başlığı hep "Video by <hesap>"; açıklamanın ilk satırı daha anlamlı.
    if platform == 'instagram' and description and (not title or title.lower().startswith('video by')):
        first_line = next((line.strip() for line in description.splitlines() if line.strip()), '')
        if first_line:
            title = first_line[:100].rstrip() + ('…' if len(first_line) > 100 else '')
    return (title or 'video')[:300]


def _probe_duration(f: dict) -> int:
    """ffprobe akışın yalnızca başını (moov) okur; hiçbir şey diske yazılmaz."""
    headers = ''.join(f'{key}: {value}\r\n' for key, value in (f.get('http_headers') or {}).items())
    cmd = [config.FFPROBE_PATH, '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0']
    if headers:
        cmd += ['-headers', headers]
    try:
        result = subprocess.run(cmd + [f['url']], capture_output=True, text=True, timeout=15)
        return int(float(result.stdout.strip() or 0))
    except (subprocess.SubprocessError, ValueError, OSError) as error:
        log.info('süre okunamadı: %s', error)
        return 0


def _pick_thumbnail(info: dict) -> tuple[str | None, dict[str, str]]:
    """JPEG tercih edilir: MP3 kapağına gömülürken en uyumlu biçim."""
    thumbs = [t for t in info.get('thumbnails') or [] if t.get('url')]
    if not thumbs:
        url = info.get('thumbnail')
        return (url, {}) if url else (None, {})

    def rank(t: dict) -> tuple:
        is_jpeg = '.jpg' in t['url'] or '.jpeg' in t['url']
        area = (t.get('width') or 0) * (t.get('height') or 0)
        return (t.get('preference') or 0, is_jpeg, area)

    best = max(thumbs, key=rank)
    return best['url'], dict(best.get('http_headers') or {})


def resolve(url: str) -> Media:
    key = cache_key(url)
    media = cache.get(key)
    if media is None:
        media = extract(url)
        cache.put(key, media)
    return media
