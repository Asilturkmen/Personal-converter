"""Parçalı okuma köprüsü (tamamen bellekte).

YouTube'un https akışları tek bir uzun istekle okunduğunda ilk ~10 MB'tan
sonra gerçek zamana yakın hıza düşürülüyor. yt-dlp bu yüzden dosyayı
`range=` parçalarıyla indiriyor; ffmpeg'in http istemcisi bunu yapamıyor.

Çözüm: ffmpeg'e CDN adresi yerine bu sunucunun loopback üzerindeki
`/internal/relay/<token>` adresi verilir. Bu uç CDN'den 10 MB'lık parçaları
sırayla çeker ve ffmpeg'e tek, kesintisiz bir akış olarak geçirir. Hiçbir
bayt diske yazılmaz; en fazla bir okuma tamponu kadar veri bellekte durur.

İki girdili (video + ses) birleştirmede ikisi de böyle beslenebilir; adlandırılmış
pipe ya da ek dosya tanımlayıcısı gerekmediği için Windows ve Linux'ta aynı çalışır.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
from collections.abc import AsyncIterator

import httpx

from media import Stream

log = logging.getLogger('converter.relay')

RETRIES = 3

_active: dict[str, Stream] = {}


def register(stream: Stream) -> str:
    token = secrets.token_urlsafe(24)
    _active[token] = stream
    return token


def unregister(token: str) -> None:
    _active.pop(token, None)


def lookup(token: str) -> Stream | None:
    return _active.get(token)


async def body(client: httpx.AsyncClient, token: str, stream: Stream) -> AsyncIterator[bytes]:
    chunk = stream.chunk_size or 10 * 1024 * 1024
    size = stream.filesize
    separator = '&' if '?' in stream.url else '?'
    position = 0

    while token in _active:
        end = position + chunk - 1
        if size:
            end = min(end, size - 1)
        wanted = end - position + 1
        got = 0

        for attempt in range(1, RETRIES + 1):
            try:
                url = f'{stream.url}{separator}range={position + got}-{end}'
                async with client.stream('GET', url, headers=stream.headers) as response:
                    response.raise_for_status()
                    async for data in response.aiter_bytes(64 * 1024):
                        got += len(data)
                        yield data
                break
            except httpx.HTTPError as error:
                # Parçanın alınmış kısmı tekrar istenmez; kalan yerden devam edilir.
                if attempt == RETRIES or token not in _active:
                    log.warning('relay parçası alınamadı (%d-%d): %s', position, end, error)
                    raise
                await asyncio.sleep(attempt)

        position += got
        if (size and position >= size) or got < wanted:
            return
