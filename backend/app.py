"""Asil Personal Converter — backend.

    yt-dlp (metadata + CDN adresleri) → ffmpeg (CDN'den okur, stdout'a yazar) → HTTP yanıtı

Sunucunun diskine hiçbir zaman hiçbir dosya yazılmaz.

Çalıştırma (backend/ klasöründe):  uvicorn app:app --port 8000
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import shutil
import sys
from contextlib import asynccontextmanager

import httpx
import yt_dlp
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import config
import downloads
import media
import thumbnails
from limits import PerKeySlots, RateLimiter, Slots
from media import Media, UserError
from names import content_disposition, safe_filename
from relay import RelayServer

# Windows konsolu cp1254 olabilir; Türkçe/Japonca başlıklar log'u çökertmesin.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-7s %(name)s: %(message)s')
log = logging.getLogger('converter')
# httpx her relay parçasını imzalı CDN adresiyle loglar; gürültü ve sızıntı.
logging.getLogger('httpx').setLevel(logging.WARNING)

info_slots = Slots(config.MAX_CONCURRENT_INFO)
info_ip_slots = PerKeySlots(config.MAX_INFO_PER_IP)
info_rate = RateLimiter(config.INFO_PER_MINUTE_PER_IP)


# --------------------------------------------------------------------------
# Açılış kontrolleri
# --------------------------------------------------------------------------

def detect_js_runtime() -> str | None:
    """yt-dlp'nin kullanacağı JS runtime'ı (varsayılan: deno) bulur."""
    try:
        ydl = yt_dlp.YoutubeDL({'quiet': True, 'cachedir': False})
        for name, runtime in ydl._js_runtimes.items():
            info = runtime.info if runtime else None
            if info is not None and info.supported is not False:
                return name
        return None
    except Exception:  # iç API değişirse PATH'e bak
        return 'deno' if shutil.which('deno') else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    if shutil.which(config.FFMPEG_PATH) is None:
        log.error('!!! ffmpeg bulunamadı (%s). İndirmeler çalışmayacak.', config.FFMPEG_PATH)

    app.state.js_runtime = detect_js_runtime()
    if app.state.js_runtime is None:
        log.error(
            '!!! yt-dlp için JavaScript runtime bulunamadı (No supported JavaScript runtime). '
            'YouTube formatlarının çoğu eksik gelecek. Deno kur: winget install -e --id DenoLand.Deno'
        )
    else:
        log.info('JS runtime: %s · yt-dlp %s', app.state.js_runtime, yt_dlp.version.__version__)

    if config.INSTAGRAM_COOKIES.is_file():
        log.info('Instagram çerezleri: %s', config.INSTAGRAM_COOKIES)
    else:
        log.info('Instagram çerez dosyası yok (%s); hikâyeler çalışmayacak.', config.INSTAGRAM_COOKIES)

    app.state.http = httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, read=30.0),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=50),
    )
    app.state.relay = RelayServer(app.state.http)
    await app.state.relay.start()
    try:
        yield
    finally:
        downloads.release_pending()
        await app.state.relay.stop()
        await app.state.http.aclose()


app = FastAPI(title='Asil Personal Converter', lifespan=lifespan, docs_url=None, redoc_url=None)


@app.exception_handler(UserError)
async def user_error_handler(request: Request, error: UserError):
    return JSONResponse({'detail': error.message}, status_code=error.status)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, error: Exception):
    log.exception('beklenmeyen hata: %s %s', request.method, request.url.path)
    return JSONResponse({'detail': 'Beklenmeyen bir hata oluştu. Tekrar dene.'}, status_code=500)


# --------------------------------------------------------------------------
# Yardımcılar
# --------------------------------------------------------------------------

def client_ip(request: Request) -> str:
    """Sınırların ve biletlerin bağlandığı istemci anahtarı.

    Reverse proxy arkasında request.client, uvicorn'un ProxyHeadersMiddleware'i
    tarafından X-Forwarded-For'dan çözülmüş hâliyle gelir; başlığa yalnızca
    FORWARDED_ALLOW_IPS'teki adreslerden gelen isteklerde güvenilir (bkz.
    config.py, serve.py). Burada ikinci bir ayrıştırma yapılmaz: iki ayrı
    mekanizma birbirinin kararını ezer.

    IPv6'da tek bir bağlantı (ev, telefon) bütün bir /64 bloğu alır ve içinden
    istediği kadar adres üretebilir; adres başına sınır böyle kolayca aşılırdı.
    Bu yüzden IPv6 istemciler /64 bloğuyla sayılır."""
    host = request.client.host if request.client else 'unknown'
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return host
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(ipaddress.IPv6Network((address, 64), strict=False))
    return host


_inflight: dict[str, asyncio.Future] = {}


async def get_media(url: str, ip: str, fresh: bool = False) -> Media:
    """fresh=True: önbellekteki kayıt (ör. CDN adresleri 403 dönmeye başladıysa)
    atılır ve video yeniden çözümlenir."""
    key = media.cache_key(url)
    if fresh:
        media.cache.drop(key)
    cached = media.cache.get(key)
    if cached is not None:
        return cached

    # Aynı video zaten çözümleniyorsa onu bekle; ikinci bir slot harcama.
    if key in _inflight:
        return await asyncio.shield(_inflight[key])

    # Sınırlar yalnızca gerçek çözümlemeye (önbellek ıskası) uygulanır.
    if not info_rate.allow(ip):
        raise UserError('Kısa sürede çok fazla bağlantı getirdin. Bir dakika bekleyip tekrar dene.', 429)
    if not info_ip_slots.try_acquire(ip):
        raise UserError('Önceki bağlantın hâlâ çözümleniyor. Birkaç saniye bekleyip tekrar dene.', 429)
    if not info_slots.try_acquire():
        info_ip_slots.release(ip)
        raise UserError(downloads.BUSY, 503)

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _inflight[key] = future
    try:
        # yt-dlp bloklayan bir kütüphane; JS runtime'ı da çalıştırdığı için
        # iş başına 0.5–2 sn tam çekirdek harcar. Event loop'u tutmasın.
        result = await run_in_threadpool(media.resolve, url)
        future.set_result(result)
        return result
    except BaseException as error:
        future.set_exception(error if isinstance(error, Exception) else UserError(downloads.BUSY, 503))
        future.exception()  # bekleyen yoksa "never retrieved" uyarısı çıkmasın
        raise
    finally:
        _inflight.pop(key, None)
        info_slots.release()
        info_ip_slots.release(ip)


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.get('/api/health')
async def health(request: Request):
    return {'ok': True, 'ytDlp': yt_dlp.version.__version__, 'jsRuntime': request.app.state.js_runtime}


@app.get('/api/info')
async def info(request: Request, url: str = ''):
    item = await get_media(media.validate_url(url), client_ip(request))
    return item.public()


@app.get('/api/thumbnail')
async def thumbnail(request: Request, url: str = '', download: bool = False):
    item = await get_media(media.validate_url(url), client_ip(request))
    thumb = await thumbnails.get(request.app.state.http, item)
    if thumb is None:
        raise UserError('Kapak görseli alınamadı.', 404)
    headers = {'Cache-Control': 'private, max-age=1800'}
    if download:
        ext = {'image/webp': 'webp', 'image/png': 'png'}.get(thumb.content_type, 'jpg')
        headers['Content-Disposition'] = content_disposition(safe_filename(item.title, ext))
    return Response(thumb.data, media_type=thumb.content_type, headers=headers)


class PrepareRequest(BaseModel):
    url: str
    format: str
    cover: bool = False
    tags: bool = False


@app.post('/api/download/prepare')
async def prepare_download(request: Request, body: PrepareRequest):
    """Yer ayırır ve ffmpeg'i başlatır; hata varsa dosya indirmesi başlamadan
    JSON olarak döner. Başarılıysa kısa ömürlü bir bilet verir."""
    url = media.validate_url(body.url)
    ip = client_ip(request)
    http = request.app.state.http
    reservation = await downloads.prepare(
        ip=ip,
        format_id=body.format,
        cover=body.cover,
        tags=body.tags,
        relay=request.app.state.relay,
        load_media=lambda fresh: get_media(url, ip, fresh=fresh),
        load_cover=lambda item: thumbnails.jpeg(http, item),
    )
    # İstemci beklerken vazgeçtiyse (iptal, sekme kapandı) yer hemen boşalsın;
    # TTL'i beklemesin.
    if await request.is_disconnected():
        reservation.release()
        return Response(status_code=499)
    return {
        'ticket': reservation.ticket,
        'filename': reservation.filename,
        'estimatedBytes': reservation.choice.estimated_bytes + len(reservation.header),
        'expiresIn': config.RESERVATION_TTL_SECONDS,
    }


@app.get('/api/download')
async def download(request: Request, ticket: str = ''):
    """Bileti (prepare'den) tüketir ve dosyayı akıtır.

    Biletsiz, tek adımlı bir indirme adresi bilerek yok: öyle bir adres başka
    sitelerden düz bir bağlantıyla kullanılabilir ve sunucunun bant genişliği
    onların indirme butonuna dönüşür. Bileti almak JSON gövdeli bir POST
    gerektirir; tarayıcı bunu başka bir origin'den CORS izni olmadan göndermez."""
    reservation = downloads.consume(ticket, client_ip(request))
    return downloads.response(reservation)


@app.delete('/api/download/{ticket}', status_code=204)
async def cancel_download(request: Request, ticket: str):
    """Kullanılmayacak bir bileti hemen serbest bırakır (kullanıcı iptal etti)."""
    downloads.cancel(ticket, client_ip(request))
    return Response(status_code=204)
