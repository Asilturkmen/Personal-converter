"""İndirme yaşam döngüsü: rezervasyon → akış → serbest bırakma.

İki adım:

  1. prepare  — slotları ayırır, formatı doğrular, ffmpeg'i başlatır ve ilk
                baytı bekler. Bir şey ters giderse JSON hata döner; dosya
                indirmesi hiç başlamamış olur. Başarılıysa kısa ömürlü bir
                bilet (ticket) verir.
  2. stream   — bileti tüketir ve yalnızca akışı yapar.

Böylece her hata (yoğunluk, IP sınırı, boyut, CDN'e erişilemedi) dosya
indirilmeye başlamadan arayüzde gösterilebilir; tarayıcının kendi
indiricisine devredilen büyük dosyalarda bile.

Kaynakların (slotlar, ffmpeg, relay biletleri) tek sahibi Reservation'dır ve
release() kaç kez çağrılırsa çağrılsın bir kez çalışır. Üç güvence vardır:
  - akış gövdesinin finally'si,
  - yanıt nesnesinin __call__ finally'si (gövde hiç başlamadan istemci
    koparsa gövdenin finally'si çalışmaz; bu çalışır),
  - tüketilmeyen biletler için TTL zamanlayıcısı.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import anyio
from starlette.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

import config
from limits import PerKeySlots, Slots
from media import Choice, Media, UserError
from names import content_disposition, safe_filename
from relay import RelayServer, RelayTicket
from stream import FFmpegStream, StreamFailed, build_command
from tags import id3_tag

log = logging.getLogger('converter.downloads')

BUSY = 'Şu an yoğunluk var, birkaç saniye sonra tekrar dene.'
FIRST_BYTE_TIMEOUT = 60
# Tahmin yaklaşıksa (HLS tepe bit hızı) ön kontrol bu kadar tolerans tanır;
# asıl koruma akış sırasındaki bayt sayacıdır.
APPROX_TOLERANCE = 1.5

download_slots = Slots(config.MAX_CONCURRENT_DOWNLOADS)
ip_slots = PerKeySlots(config.MAX_DOWNLOADS_PER_IP)

_pending: dict[str, Reservation] = {}


@dataclass(eq=False)
class Reservation:
    ip: str
    item: Media
    choice: Choice
    relay: RelayServer
    ticket: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    relays: list[RelayTicket] = field(default_factory=list)
    proc: FFmpegStream | None = None
    header: bytes = b''
    first: bytes = b''
    expiry: asyncio.TimerHandle | None = None
    consumed: bool = False
    _released: bool = False

    @property
    def ext(self) -> str:
        return 'mp3' if self.choice.kind == 'audio' else 'mp4'

    @property
    def filename(self) -> str:
        return safe_filename(self.item.title, self.ext)

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self.expiry:
            self.expiry.cancel()
        _pending.pop(self.ticket, None)
        if self.proc:
            self.proc.close()
        for ticket in self.relays:
            self.relay.unregister(ticket)
        download_slots.release()
        ip_slots.release(self.ip)


async def prepare(
    *,
    ip: str,
    format_id: str,
    cover: bool,
    tags: bool,
    relay: RelayServer,
    load_media: Callable[[], Awaitable[Media]],
    load_cover: Callable[[Media], Awaitable[bytes | None]],
) -> Reservation:
    """Başarılı dönerse slotlar ayrılmış ve ffmpeg ilk baytı üretmiştir.
    Hata olursa her şey serbest bırakılmış olarak UserError yükselir."""
    # Sınırlar ağır işten (çözümleme, ffmpeg) önce kontrol edilir.
    if not ip_slots.try_acquire(ip):
        raise UserError('Zaten devam eden bir indirmen var. O bitince yenisini başlat.', 429)
    if not download_slots.try_acquire():
        ip_slots.release(ip)
        raise UserError(BUSY, 503)

    reservation: Reservation | None = None
    try:
        item = await load_media()
        choice = item.choices.get(format_id)
        if choice is None:
            raise UserError('Bu format bu video için mevcut değil. Bağlantıyı yeniden getir.', 400)

        limit = config.MAX_BYTES * (1 if choice.size_exact else APPROX_TOLERANCE)
        if choice.estimated_bytes > limit:
            megabytes = config.MAX_BYTES // (1024 * 1024)
            raise UserError(f'Dosya çok büyük (sınır {megabytes} MB). Daha düşük bir çözünürlük seç.', 413)

        reservation = Reservation(ip=ip, item=item, choice=choice, relay=relay)

        # Parçalı okunması gereken girdiler loopback relay'den beslenir.
        relay_urls: list[str | None] = []
        for source in choice.inputs:
            if source.chunk_size:
                ticket = relay.register(source)
                reservation.relays.append(ticket)
                relay_urls.append(relay.url(ticket))
            else:
                relay_urls.append(None)

        # MP3 etiketi bellekte hazırlanıp akışın başına eklenir (bkz. tags.py).
        if choice.kind == 'audio' and (cover or tags):
            reservation.header = id3_tag(
                title=item.title if tags else None,
                artist=item.uploader if tags else None,
                cover=await load_cover(item) if cover else None,
            )

        reservation.proc = FFmpegStream(build_command(choice, relay_urls=relay_urls))
        reservation.proc.start()

        # İlk bayt gelmeden bilet verilmez: ffmpeg kaynağı açamazsa kullanıcı
        # boş bir dosya yerine anlaşılır bir hata görür.
        with anyio.move_on_after(FIRST_BYTE_TIMEOUT):
            reservation.first = await anyio.to_thread.run_sync(reservation.proc.read, abandon_on_cancel=True)
        if not reservation.first:
            log.warning('ffmpeg başlamadı: %s', reservation.proc.error_text())
            raise UserError('İndirme başlatılamadı. Birkaç saniye sonra tekrar dene; sürerse bağlantıyı yeniden getir.', 502)
    except BaseException:
        if reservation:
            reservation.release()
        else:
            download_slots.release()
            ip_slots.release(ip)
        raise

    _pending[reservation.ticket] = reservation
    reservation.expiry = asyncio.get_running_loop().call_later(config.RESERVATION_TTL_SECONDS, _expire, reservation)
    return reservation


def _expire(reservation: Reservation) -> None:
    if not reservation.consumed:
        log.info('bilet kullanılmadı, süresi doldu: %s', reservation.item.title)
        reservation.release()


def consume(ticket: str, ip: str) -> Reservation:
    reservation = _pending.get(ticket)
    # Bilet onu alan IP'ye bağlıdır; başkasına sızsa da kullanılamaz.
    if reservation is None or reservation.ip != ip:
        raise UserError('İndirme bağlantısının süresi doldu. Tekrar dene.', 410)
    _pending.pop(ticket, None)
    reservation.consumed = True
    if reservation.expiry:
        reservation.expiry.cancel()
    return reservation


def cancel(ticket: str, ip: str) -> None:
    reservation = _pending.get(ticket)
    if reservation is not None and reservation.ip == ip:
        reservation.release()


class _ManagedStreamingResponse(StreamingResponse):
    def __init__(self, *args, on_close: Callable[[], None], **kwargs):
        super().__init__(*args, **kwargs)
        self._on_close = on_close

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        except StreamFailed:
            # Nedeni stream/_check_relays zaten logladı. Yanıt tamamlanmadan
            # dönüldüğü için sunucu bağlantıyı son parçayı göndermeden kapatır;
            # istemci akışı eksik görür. Beklenen bir durum, traceback basılmaz.
            pass
        finally:
            self._on_close()


def response(reservation: Reservation) -> StreamingResponse:
    headers = {
        'Content-Disposition': content_disposition(reservation.filename),
        'Cache-Control': 'no-store',
        'X-Accel-Buffering': 'no',
        'X-Estimated-Bytes': str(reservation.choice.estimated_bytes + len(reservation.header)),
        # Content-Length bilerek yok: tahmin gerçek boyuttan saparsa indirme bozulur.
    }
    return _ManagedStreamingResponse(
        _body(reservation),
        media_type='audio/mpeg' if reservation.ext == 'mp3' else 'video/mp4',
        headers=headers,
        on_close=reservation.release,
    )


async def _body(reservation: Reservation):
    proc = reservation.proc
    assert proc is not None
    try:
        if reservation.header:
            yield reservation.header
        yield reservation.first
        while True:
            chunk = await anyio.to_thread.run_sync(proc.read, abandon_on_cancel=True)
            if not chunk:
                break
            yield chunk

        # Hata varsa StreamFailed yükselir ve bağlantı temiz kapanmaz;
        # tarayıcı yarım dosyayı tamamlanmış saymaz.
        await anyio.to_thread.run_sync(proc.finish)
        await _check_relays(reservation.relays)
        log.info('indirme bitti: %s %s (%d bayt)', reservation.choice.id, reservation.item.title, proc.bytes_sent)
    finally:
        # İstemci koptuğunda da buraya düşülür: ffmpeg öldürülür.
        reservation.release()


async def _check_relays(relays: list[RelayTicket]) -> None:
    """ffmpeg 0 ile çıksa bile her relay girdisi sonuna kadar teslim edilmiş olmalı."""
    # Relay son baytı yazdıktan sonra durumunu işaretler; ffmpeg bundan
    # önce bitmiş olabilir. Kısa bir süre durumun netleşmesi beklenir.
    for _ in range(40):
        if all(ticket.completed or ticket.failed for ticket in relays):
            break
        await asyncio.sleep(0.05)
    broken = [ticket for ticket in relays if not ticket.ok]
    if broken:
        detail = ', '.join(f'{t.bytes_sent}/{t.stream.filesize or "?"} bayt' for t in broken)
        log.warning('akış başarısız: relay girdisi eksik (%s)', detail)
        raise StreamFailed('relay girdisi eksik')
