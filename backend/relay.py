"""Parçalı okuma köprüsü (tamamen bellekte).

YouTube'un https akışları tek bir uzun istekle okunduğunda ilk ~10 MB'tan
sonra gerçek zamana yakın hıza düşürülüyor. yt-dlp bu yüzden dosyayı
`range=` parçalarıyla indiriyor; ffmpeg'in http istemcisi bunu yapamıyor.

Çözüm: ffmpeg'e CDN adresi yerine `http://127.0.0.1:<port>/<token>` verilir.
Bu adreste, uygulamanın kendisinden bağımsız küçük bir HTTP sunucusu dinler;
CDN'den 10 MB'lık parçaları sırayla çekip ffmpeg'e tek, kesintisiz bir akış
olarak geçirir. Hiçbir bayt diske yazılmaz.

Neden uygulamanın kendi portu değil de ayrı bir loopback sunucusu?
  - Her worker süreci kendi sunucusunu açar; token'ı kaydeden süreç ile
    ffmpeg'in bağlandığı süreç her zaman aynıdır (çok worker'da da çalışır).
  - uvicorn unix socket (--uds) üzerinden dinlese de çalışır.
  - Dışarıdan erişilemez: yalnızca 127.0.0.1'e bağlıdır, reverse proxy
    arkasından hiçbir yol buraya çıkmaz.

Bütünlük: ffmpeg yarıda kesilen bir http girdisini çoğu zaman "partial file"
uyarısıyla geçip çıkış kodu 0 ile bitiyor. Bu yüzden her bilet, akışın
sonuna kadar eksiksiz teslim edilip edilmediğini kaydeder; indirme sonunda
stream katmanı buna bakar ve eksik bir girdi varsa akışı hata olarak keser.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from media import Stream

log = logging.getLogger('converter.relay')

RETRIES = 3
DEFAULT_CHUNK = 10 * 1024 * 1024
READ_SIZE = 64 * 1024
# CDN bir parçanın ortasında bu kadar susarsa parça kaldığı yerden yeniden
# istenir. ffmpeg relay girdisinde 30 sn veri gelmezse vazgeçiyor
# (stream.IO_TIMEOUT); yeniden deneme ancak ondan önce devreye girerse işe yarar
# (ölçüldü: 35 sn susan bir parçada 30 sn → indirme başarısız, 10 sn → tamamlandı).
CHUNK_TIMEOUT = httpx.Timeout(10.0)


@dataclass(eq=False)
class RelayTicket:
    token: str
    stream: Stream
    # Kaynak dosyanın son baytı ffmpeg'e yazıldı mı?
    completed: bool = False
    # Kaynağa ulaşılamadı (tüm denemeler tükendi). ffmpeg'in bağlantıyı
    # kendisi kapatması hata sayılmaz.
    failed: bool = False
    bytes_sent: int = 0

    @property
    def ok(self) -> bool:
        return self.completed and not self.failed


class RelayServer:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self._tickets: dict[str, RelayTicket] = {}
        self._server: asyncio.base_events.Server | None = None
        self.port: int | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, host='127.0.0.1', port=0)
        self.port = self._server.sockets[0].getsockname()[1]
        log.info('relay: 127.0.0.1:%d', self.port)

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    def register(self, stream: Stream) -> RelayTicket:
        ticket = RelayTicket(token=secrets.token_urlsafe(24), stream=stream)
        self._tickets[ticket.token] = ticket
        return ticket

    def unregister(self, ticket: RelayTicket) -> None:
        self._tickets.pop(ticket.token, None)

    def url(self, ticket: RelayTicket) -> str:
        return f'http://127.0.0.1:{self.port}/{ticket.token}'

    # ------------------------------------------------------------------
    # Minimal HTTP/1.1: yalnızca ffmpeg'in yaptığı tek GET isteği.
    # ------------------------------------------------------------------

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=10)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError):
            writer.close()
            return

        request_line = head.split(b'\r\n', 1)[0].decode('latin-1')
        parts = request_line.split(' ')
        token = parts[1].lstrip('/') if len(parts) >= 2 and parts[0] == 'GET' else ''
        ticket = self._tickets.get(token)
        if ticket is None:
            writer.write(b'HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            await _close(writer)
            return

        size = ticket.stream.filesize
        # Gövdenin nerede bittiği ffmpeg'e her zaman söylenir: boyut biliniyorsa
        # Content-Length, bilinmiyorsa chunked. İkisi de yoksa ffmpeg bağlantının
        # kapanmasını "Stream ends prematurely" diye hata sayıyor ve eksiksiz
        # inen dosya %100'de başarısız görünüyordu (ölçüldü: YouTube itag 18,
        # boyutu bildirilmiyor). Range desteği yok ve duyurulmuyor; ffmpeg akışı
        # baştan sona tek seferde okur.
        headers = 'HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nConnection: close\r\n'
        headers += f'Content-Length: {size}\r\n' if size else 'Transfer-Encoding: chunked\r\n'
        writer.write((headers + '\r\n').encode('latin-1'))

        try:
            async for data in self._upstream(ticket):
                if not data:
                    continue  # chunked'da boş parça gövdenin sonu demek
                writer.write(data if size else b'%x\r\n%b\r\n' % (len(data), data))
                await writer.drain()
                ticket.bytes_sent += len(data)
            if not size:
                writer.write(b'0\r\n\r\n')
                await writer.drain()
            ticket.completed = True
        except (ConnectionError, _Abandoned):
            # ffmpeg bağlantıyı kapattı (öldürüldü ya da bitti) veya indirme iptal edildi.
            pass
        except httpx.HTTPError as error:
            ticket.failed = True
            log.warning('relay kaynağa ulaşamadı (%d bayt sonra): %s', ticket.bytes_sent, error)
            writer.transport.abort()  # temiz kapanış değil: ffmpeg de hata görsün
            return
        await _close(writer)

    async def _upstream(self, ticket: RelayTicket) -> AsyncIterator[bytes]:
        stream = ticket.stream
        chunk = stream.chunk_size or DEFAULT_CHUNK
        size = stream.filesize
        separator = '&' if '?' in stream.url else '?'
        position = 0

        while ticket.token in self._tickets:
            end = position + chunk - 1
            if size:
                end = min(end, size - 1)
            wanted = end - position + 1
            got = 0

            for attempt in range(1, RETRIES + 1):
                try:
                    url = f'{stream.url}{separator}range={position + got}-{end}'
                    async with self.client.stream('GET', url, headers=stream.headers, timeout=CHUNK_TIMEOUT) as response:
                        if response.status_code == 416:  # boyut bilinmiyordu, dosya tam bölündü
                            return
                        response.raise_for_status()
                        async for data in response.aiter_bytes(READ_SIZE):
                            got += len(data)
                            yield data
                    break
                except httpx.HTTPError:
                    # Parçanın alınmış kısmı tekrar istenmez; kalan yerden devam edilir.
                    if attempt == RETRIES or ticket.token not in self._tickets:
                        raise
                    await asyncio.sleep(attempt)

            position += got
            if size and position >= size:
                return
            if not size and got < wanted:
                return
            if size and got < wanted:
                # Sunucu parçayı eksik ve hatasız kapattı: dosya beklenenden kısa.
                raise httpx.RemoteProtocolError(f'parça eksik: {got}/{wanted} bayt')

        # Bilet iptal edildi (indirme bitti ya da iptal): tamamlanmış sayılmaz.
        raise _Abandoned


class _Abandoned(Exception):
    """İndirme relay'i beklemeden kapandı; kaynak hatası değil."""


async def _close(writer: asyncio.StreamWriter) -> None:
    try:
        writer.close()
        await writer.wait_closed()
    except (ConnectionError, OSError):
        pass
