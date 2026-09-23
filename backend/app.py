"""Asil Personal Converter — backend.

    yt-dlp (metadata + CDN adresleri) → ffmpeg (CDN'den okur, stdout'a yazar) → HTTP yanıtı

Sunucunun diskine hiçbir zaman hiçbir dosya yazılmaz.

Çalıştırma (backend/ klasöründe):  uvicorn app:app --port 8000
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
from contextlib import asynccontextmanager

import anyio
import httpx
import yt_dlp
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

import config
import media
import relay
from limits import PerKeySlots, Slots
from media import Media, UserError
from names import content_disposition, safe_filename
from stream import FFmpegStream, build_command
from tags import id3_tag, to_jpeg

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

BUSY = 'Şu an yoğunluk var, birkaç saniye sonra tekrar dene.'
FIRST_BYTE_TIMEOUT = 60
THUMBNAIL_MAX_BYTES = 8 * 1024 * 1024

download_slots = Slots(config.MAX_CONCURRENT_DOWNLOADS)
info_slots = Slots(config.MAX_CONCURRENT_INFO)
ip_slots = PerKeySlots(config.MAX_DOWNLOADS_PER_IP)


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
    try:
        yield
    finally:
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
    # Not: sunucuya taşınınca nginx arkasında X-Forwarded-For'a bakılmalı.
    return request.client.host if request.client else 'unknown'


_inflight: dict[str, asyncio.Future] = {}


async def get_media(url: str) -> Media:
    key = media.cache_key(url)
    cached = media.cache.get(key)
    if cached is not None:
        return cached

    # Aynı video zaten çözümleniyorsa onu bekle; ikinci bir slot harcama.
    if key in _inflight:
        return await asyncio.shield(_inflight[key])

    if not info_slots.try_acquire():
        raise UserError(BUSY, 503)
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _inflight[key] = future
    try:
        # yt-dlp bloklayan bir kütüphane; JS runtime'ı da çalıştırdığı için
        # iş başına 0.5–2 sn tam çekirdek harcar. Event loop'u tutmasın.
        result = await run_in_threadpool(media.resolve, url)
        future.set_result(result)
        return result
    except BaseException as error:
        future.set_exception(error if isinstance(error, Exception) else UserError(BUSY, 503))
        future.exception()  # bekleyen yoksa "never retrieved" uyarısı çıkmasın
        raise
    finally:
        _inflight.pop(key, None)
        info_slots.release()


async def fetch_thumbnail(client: httpx.AsyncClient, item: Media) -> tuple[bytes, str] | None:
    if not item.thumbnail:
        return None
    try:
        async with client.stream('GET', item.thumbnail, headers=item.thumbnail_headers) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data += chunk
                if len(data) > THUMBNAIL_MAX_BYTES:
                    return None
            return bytes(data), response.headers.get('content-type', 'image/jpeg').split(';')[0]
    except httpx.HTTPError as error:
        log.info('kapak alınamadı: %s', error)
        return None


# --------------------------------------------------------------------------
# API
# --------------------------------------------------------------------------

@app.get('/api/health')
async def health(request: Request):
    return {'ok': True, 'ytDlp': yt_dlp.version.__version__, 'jsRuntime': request.app.state.js_runtime}


@app.get('/api/info')
async def info(url: str = ''):
    item = await get_media(media.validate_url(url))
    return item.public()


@app.get('/api/thumbnail')
async def thumbnail(request: Request, url: str = '', download: bool = False):
    item = await get_media(media.validate_url(url))
    result = await fetch_thumbnail(request.app.state.http, item)
    if result is None:
        raise UserError('Kapak görseli alınamadı.', 404)
    data, content_type = result
    headers = {'Cache-Control': 'private, max-age=1800'}
    if download:
        ext = {'image/webp': 'webp', 'image/png': 'png'}.get(content_type, 'jpg')
        headers['Content-Disposition'] = content_disposition(safe_filename(item.title, ext))
    return Response(data, media_type=content_type, headers=headers)


@app.get('/api/download')
async def download(
    request: Request,
    url: str = '',
    format: str = '',
    cover: bool = False,
    tags: bool = False,
):
    url = media.validate_url(url)
    ip = client_ip(request)

    if not ip_slots.try_acquire(ip):
        raise UserError('Zaten devam eden bir indirmen var. O bitince yenisini başlat.', 429)
    if not download_slots.try_acquire():
        ip_slots.release(ip)
        raise UserError(BUSY, 503)

    tokens: list[str] = []
    proc: FFmpegStream | None = None

    def cleanup() -> None:
        if proc is not None:
            proc.close()
        for token in tokens:
            relay.unregister(token)
        download_slots.release()
        ip_slots.release(ip)

    try:
        item = await get_media(url)
        choice = item.choices.get(format)
        if choice is None:
            raise UserError('Bu format bu video için mevcut değil. Bağlantıyı yeniden getir.', 400)
        if choice.estimated_bytes > config.MAX_BYTES:
            limit = config.MAX_BYTES // (1024 * 1024)
            raise UserError(f'Dosya çok büyük (sınır {limit} MB). Daha düşük bir çözünürlük seç.', 413)

        # Parçalı okunması gereken girdiler loopback relay üzerinden beslenir.
        port = (request.scope.get('server') or ('127.0.0.1', 8000))[1]
        relay_urls: list[str | None] = []
        for source in choice.inputs:
            if source.chunk_size:
                token = relay.register(source)
                tokens.append(token)
                relay_urls.append(f'http://127.0.0.1:{port}/internal/relay/{token}')
            else:
                relay_urls.append(None)

        # MP3 etiketi bellekte hazırlanıp akışın başına eklenir (bkz. tags.py).
        header = b''
        if choice.kind == 'audio' and (cover or tags):
            cover_jpeg = None
            if cover:
                fetched = await fetch_thumbnail(request.app.state.http, item)
                if fetched:
                    cover_jpeg = await run_in_threadpool(to_jpeg, *fetched)
            header = id3_tag(
                title=item.title if tags else None,
                artist=item.uploader if tags else None,
                cover=cover_jpeg,
            )

        proc = FFmpegStream(build_command(choice, relay_urls=relay_urls))
        proc.start()

        # İlk baytı yanıt başlamadan bekle: ffmpeg CDN'i açamazsa kullanıcı
        # boş bir dosya yerine anlaşılır bir hata görür.
        first = b''
        with anyio.move_on_after(FIRST_BYTE_TIMEOUT):
            first = await anyio.to_thread.run_sync(proc.read, abandon_on_cancel=True)
        if not first:
            log.warning('ffmpeg başlamadı: %s', proc.error_text())
            raise UserError('İndirme başlatılamadı. Birkaç saniye sonra tekrar dene; sürerse bağlantıyı yeniden getir.', 502)
    except BaseException:
        cleanup()
        raise

    async def body():
        try:
            if header:
                yield header
            yield first
            while True:
                chunk = await anyio.to_thread.run_sync(proc.read, abandon_on_cancel=True)
                if not chunk:
                    break
                yield chunk
            # Hata varsa StreamFailed yükselir ve bağlantı temiz kapanmaz;
            # tarayıcı yarım dosyayı tamamlanmış saymaz.
            await anyio.to_thread.run_sync(proc.finish)
            log.info('indirme bitti: %s %s (%d bayt)', format, item.title, proc.bytes_sent)
        finally:
            # İstemci koptuğunda da buraya düşülür: ffmpeg öldürülür.
            cleanup()

    ext = 'mp3' if choice.kind == 'audio' else 'mp4'
    headers = {
        'Content-Disposition': content_disposition(safe_filename(item.title, ext)),
        'Cache-Control': 'no-store',
        'X-Accel-Buffering': 'no',
        'X-Estimated-Bytes': str(choice.estimated_bytes),
        # Content-Length bilerek yok: tahmin gerçek boyuttan saparsa indirme bozulur.
    }
    return StreamingResponse(body(), media_type='audio/mpeg' if ext == 'mp3' else 'video/mp4', headers=headers)


# --------------------------------------------------------------------------
# İç uç: ffmpeg'i CDN'den parça parça besler (bkz. relay.py)
# /api dışında durur; dışarıya proxy'lenmez.
# --------------------------------------------------------------------------

@app.get('/internal/relay/{token}')
async def relay_endpoint(request: Request, token: str):
    if client_ip(request) not in ('127.0.0.1', '::1'):
        return Response(status_code=404)
    source = relay.lookup(token)
    if source is None:
        return Response(status_code=404)
    return StreamingResponse(
        relay.body(request.app.state.http, token, source),
        media_type='application/octet-stream',
    )
