"""Asil Personal Converter — backend.

    yt-dlp (metadata + CDN adresleri) → ffmpeg (CDN'den okur, stdout'a yazar) → HTTP yanıtı

Sunucunun diskine hiçbir zaman hiçbir dosya yazılmaz.

Çalıştırma (backend/ klasöründe):  python serve.py
(tek worker, .env ayarları, sınırlı kapanış süresi; bkz. serve.py)
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import shutil
import sys
import time
from collections.abc import Awaitable
from contextlib import asynccontextmanager
from typing import TypeVar
from urllib.parse import urljoin

import anyio
import httpx
import yt_dlp
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.types import ASGIApp, Receive, Scope, Send

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

RATE_LIMITED = 'Kısa sürede çok fazla bağlantı getirdin. Bir dakika bekleyip tekrar dene.'
# Normal bir çözümleme 2–5 sn; Instagram'da süre ölçümüyle (ffprobe) 20 sn'ye çıkabilir.
RESOLVE_TIMEOUT_SECONDS = 90
DISCONNECT_POLL_SECONDS = 0.5

T = TypeVar('T')


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


# --------------------------------------------------------------------------
# Yalnızca kendi arayüzünden
# --------------------------------------------------------------------------

class SameOriginOnly:
    """Başka bir sitenin sayfasından gelen tarayıcı isteklerini reddeder.

    CORS başka sitelerin yanıtı okumasını engeller, isteğin gönderilmesini
    engellemez: başka bir sayfaya konan <img src=".../api/info?url=..."> o
    sayfanın her ziyaretçisinde burada bir yt-dlp çözümlemesi başlatır,
    çözümleme slotlarını doldurur ve sunucunun IP'sini YouTube'un gözünde
    yıpratır. Kapaklar da aynı yolla başka sitelere gömülebilirdi.

    Sec-Fetch-Site'ı tarayıcı koyar, sayfanın JavaScript'i değiştiremez:
    `same-origin` kendi arayüzümüz, `none` adres çubuğuna yazılan adres.
    Başlık yoksa (curl, eski tarayıcı) istek geçer; tarayıcı dışı bir istemci
    başlığı zaten istediği gibi yazar, ona karşı koruma IP sınırlarıdır.

    Origin ile Host karşılaştırılmıyor: reverse proxy Host'u değiştirebilir
    (nginx'in varsayılanı $proxy_host) ve bu, kendi arayüzümüzü engellerdi.
    Saf ASGI: BaseHTTPMiddleware akış yanıtlarını araya alıp yeniden akıtır."""

    ALLOWED = frozenset({b'same-origin', b'none'})

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'http':
            site = dict(scope['headers']).get(b'sec-fetch-site')
            if site is not None and site not in self.ALLOWED:
                response = JSONResponse({'detail': 'Bu servis yalnızca kendi sayfasından kullanılabilir.'}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


app = FastAPI(title='Asil Personal Converter', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SameOriginOnly)


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


_inflight: dict[str, asyncio.Task] = {}


async def get_media(url: str, ip: str, fresh: bool = False) -> Media:
    """fresh=True: önbellekteki kayıt (ör. CDN adresleri 403 dönmeye başladıysa)
    atılır ve video yeniden çözümlenir.

    Çözümleme isteği yapanın değil, ayrı bir görevin işidir: istek iptal edilse
    de (kullanıcı prepare'i bıraktı) aynı videoyu bekleyen diğer istekler
    etkilenmez, sonuç yine önbelleğe yazılır."""
    key = media.cache_key(url)
    if fresh:
        media.cache.drop(key)
    cached = media.cache.get(key)
    if cached is not None:
        return cached

    # Aynı video zaten çözümleniyorsa onu bekle; ikinci bir slot harcama.
    task = _inflight.get(key)
    if task is None:
        # Sınırlar yalnızca gerçek çözümlemeye (önbellek ıskası) uygulanır.
        if not info_rate.allow(ip):
            raise UserError(RATE_LIMITED, 429)
        if not info_ip_slots.try_acquire(ip):
            raise UserError('Önceki bağlantın hâlâ çözümleniyor. Birkaç saniye bekleyip tekrar dene.', 429)
        if not info_slots.try_acquire():
            info_ip_slots.release(ip)
            raise UserError(downloads.BUSY, 503)
        task = asyncio.create_task(_resolve(url, key, ip))
        # Bekleyen kalmadıysa "exception was never retrieved" uyarısı çıkmasın.
        task.add_done_callback(lambda done: done.cancelled() or done.exception())
        _inflight[key] = task

    # asyncio.wait bekleyen iptal edilse de görevi iptal etmez. shield de etmez,
    # ama Python 3.13+ bekleyeni gitmiş görevin olağan hatalarını ("Video çok
    # uzun") ERROR ve traceback ile logluyor.
    try:
        with anyio.fail_after(RESOLVE_TIMEOUT_SECONDS):
            await asyncio.wait({task})
    except TimeoutError:
        log.warning('çözümleme %d sn içinde bitmedi: %s', RESOLVE_TIMEOUT_SECONDS, url)
        raise UserError('Video bilgisi zamanında alınamadı. Biraz sonra tekrar dene.', 504) from None
    return task.result()


async def _resolve(url: str, key: str, ip: str) -> Media:
    """yt-dlp bloklayan bir kütüphane; JS runtime'ı da çalıştırdığı için iş başına
    0.5–2 sn tam çekirdek harcar, event loop'u tutmasın diye thread'de çalışır.

    Slotlar thread gerçekten bitince bırakılır. yt-dlp'nin Deno çağrısının zaman
    aşımı yok ve takılan bir thread durdurulamaz: bekleyen istek RESOLVE_TIMEOUT
    sonra hata alır, ama slot dolu kalır. Aksi hâlde takılan her çözümleme bir
    thread ve bir Deno süreci bırakıp yenisine yer açar, bellek sınırsız dolardı.
    (abandon_on_cancel yalnızca kapanışta işe yarar; bu görevi başka kimse iptal
    etmez.)"""
    started = time.monotonic()
    try:
        return await anyio.to_thread.run_sync(media.resolve, url, abandon_on_cancel=True)
    finally:
        _inflight.pop(key, None)
        info_slots.release()
        info_ip_slots.release(ip)
        elapsed = time.monotonic() - started
        if elapsed > RESOLVE_TIMEOUT_SECONDS:
            log.warning('çözümleme %.0f sn sonra bitti, slot şimdi boşaldı: %s', elapsed, url)


async def unless_disconnected(request: Request, work: Awaitable[T]) -> T | None:
    """İşi yürütür; istemci beklerken vazgeçerse (iptal, sekme kapandı) işi
    iptal edip None döner. prepare'in beklemeleri (reklam süresi, ilk bayt,
    taze çözümleme) böylece gitmiş bir istemci için dakikalarca yer tutmaz.
    İptal güvenli: prepare hata ya da iptalde her şeyi kendisi bırakır."""
    task = asyncio.ensure_future(work)
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=DISCONNECT_POLL_SECONDS)
            if not task.done() and await request.is_disconnected():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                return None
        return task.result()
    except asyncio.CancelledError:
        task.cancel()
        raise


async def open_share_link(http: httpx.AsyncClient, share: str, ip: str) -> str:
    """Instagram'ın /share/ kısa bağlantısını gönderinin asıl adresine çevirir.

    Instagram asıl adresi tarayıcı olmayan istemcilere 302 ile söylüyor
    (tarayıcıya JavaScript'li bir sayfa dönüyor). Tek istek atılır, yönlendirme
    izlenmez; yalnızca Location okunur ve o adres de olağan doğrulamadan geçer."""
    if not info_rate.allow(ip):
        raise UserError(RATE_LIMITED, 429)
    try:
        response = await http.head(share, follow_redirects=False)
    except httpx.HTTPError as error:
        log.info('paylaşım bağlantısı açılamadı (%s): %s', share, error)
        raise UserError('Instagram şu an yanıt vermiyor. Biraz sonra tekrar dene.', 502) from None

    location = response.headers.get('location', '') if response.is_redirect else ''
    target = urljoin(share, location) if location else ''
    if not target or not media.cache_key(target).startswith('ig:'):
        log.info('paylaşım bağlantısı gönderiye yönlenmedi (%s): %d %s', share, response.status_code, location)
        raise UserError('Bu paylaşım bağlantısı açılamadı. Gönderiyi Instagram\'da açıp bağlantısını oradan kopyala.', 422)
    return target


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.get('/api/health')
async def health(request: Request):
    return {'ok': True, 'ytDlp': yt_dlp.version.__version__, 'jsRuntime': request.app.state.js_runtime}


@app.get('/api/info')
async def info(request: Request, url: str = ''):
    """Yanıttaki `url` bağlantının temizlenmiş hâlidir; arayüz kapak ve indirme
    için bunu kullanır. /share/ kısa bağlantıları bu yüzden yalnızca burada açılır."""
    ip = client_ip(request)
    if share := media.share_link(url):
        url = await open_share_link(request.app.state.http, share, ip)
    item = await get_media(media.validate_url(url), ip)
    return item.public()


@app.get('/api/thumbnail')
async def thumbnail(request: Request, url: str = '', download: bool = False):
    item = await get_media(media.validate_url(url), client_ip(request))
    thumb = await thumbnails.get(request.app.state.http, item)
    if thumb is None:
        raise UserError('Kapak görseli alınamadı.', 404)
    # nosniff: görsel olarak işaretlenen yanıt başka bir türde yorumlanmasın.
    headers = {'Cache-Control': 'private, max-age=1800', 'X-Content-Type-Options': 'nosniff'}
    if download:
        ext = {'image/webp': 'webp', 'image/png': 'png', 'image/avif': 'avif', 'image/gif': 'gif'}.get(thumb.content_type, 'jpg')
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
    reservation = await unless_disconnected(request, downloads.prepare(
        ip=ip,
        format_id=body.format,
        cover=body.cover,
        tags=body.tags,
        relay=request.app.state.relay,
        load_media=lambda fresh: get_media(url, ip, fresh=fresh),
        load_cover=lambda item: thumbnails.jpeg(http, item),
    ))
    # Son anda koptuysa da bilet kimseye verilmez; yer TTL'i beklemeden boşalır.
    if reservation is not None and await request.is_disconnected():
        reservation.release()
        reservation = None
    if reservation is None:
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
