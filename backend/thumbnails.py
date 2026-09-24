"""Kapak görselleri: CDN'den bellekte alınır, bellekte önbelleklenir.

Aynı kapak hem sayfada, hem "Kapak görselini indir"de, hem MP3 etiketinde
kullanılır; her seferinde CDN'e gidilmez. Önbellek toplam bayt ile sınırlı
(LRU) ve bilgi önbelleğiyle aynı TTL'e sahip. Diske hiçbir şey yazılmaz.
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict

import httpx
from starlette.concurrency import run_in_threadpool

import config
from media import Media, cache_key
from tags import to_jpeg

log = logging.getLogger('converter.thumbnails')

MAX_IMAGE_BYTES = 8 * 1024 * 1024
# Kapaklar bizim origin'imizden sunuluyor; SVG gibi betik taşıyabilen türler
# hiç kabul edilmez. YouTube jpeg/webp, Instagram jpeg veriyor.
IMAGE_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'})


class Thumbnail:
    __slots__ = ('data', 'content_type', 'jpeg')

    def __init__(self, data: bytes, content_type: str):
        self.data = data
        self.content_type = content_type
        self.jpeg: bytes | None = data if content_type == 'image/jpeg' else None


class ThumbnailCache:
    def __init__(self, max_bytes: int, ttl: int):
        self.max_bytes = max_bytes
        self.ttl = ttl
        self._items: OrderedDict[str, tuple[float, Thumbnail, int]] = OrderedDict()
        self._size = 0

    def get(self, key: str) -> Thumbnail | None:
        item = self._items.get(key)
        if item is None:
            return None
        stored_at, thumb, _ = item
        if time.monotonic() - stored_at > self.ttl:
            self._drop(key)
            return None
        self._items.move_to_end(key)
        return thumb

    def put(self, key: str, thumb: Thumbnail) -> None:
        self._drop(key)
        cost = _cost(thumb)
        if cost > self.max_bytes:
            return
        # Maliyet eklendiği andaki hâliyle saklanır; çıkarılırken aynısı düşülür.
        self._items[key] = (time.monotonic(), thumb, cost)
        self._size += cost
        while self._size > self.max_bytes:
            self._drop(next(iter(self._items)))

    def _drop(self, key: str) -> None:
        item = self._items.pop(key, None)
        if item:
            self._size -= item[2]


def _cost(thumb: Thumbnail) -> int:
    extra = len(thumb.jpeg) if thumb.jpeg is not None and thumb.jpeg is not thumb.data else 0
    return len(thumb.data) + extra


_cache = ThumbnailCache(config.THUMBNAIL_CACHE_MEGABYTES * 1024 * 1024, config.CACHE_TTL_SECONDS)


async def get(client: httpx.AsyncClient, item: Media) -> Thumbnail | None:
    key = cache_key(item.url)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    # yt-dlp'nin adayları doğrulanmamış adreslerdir; sağlam olan bulunana
    # kadar sırayla denenir (ör. maxresdefault.webp 404 → maxresdefault.jpg).
    for url, headers in item.thumbnails:
        thumb = await _fetch(client, url, headers)
        if thumb is not None:
            _cache.put(key, thumb)
            return thumb
    if item.thumbnails:
        log.info('kapak alınamadı: %d adayın hiçbiri açılmadı (%s)', len(item.thumbnails), item.url)
    return None


async def _fetch(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> Thumbnail | None:
    try:
        async with client.stream('GET', url, headers=headers) as response:
            if response.status_code != 200:
                return None
            content_type = response.headers.get('content-type', 'image/jpeg').split(';')[0].strip().lower()
            if content_type == 'image/jpg':  # standart dışı ama görülen yazım
                content_type = 'image/jpeg'
            if content_type not in IMAGE_TYPES:
                return None
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data += chunk
                if len(data) > MAX_IMAGE_BYTES:
                    return None
    except httpx.HTTPError:
        return None
    return Thumbnail(bytes(data), content_type)


async def jpeg(client: httpx.AsyncClient, item: Media) -> bytes | None:
    """MP3 etiketi için JPEG kapak (WebP'ler bir kez çevrilip saklanır)."""
    thumb = await get(client, item)
    if thumb is None:
        return None
    if thumb.jpeg is None:
        thumb.jpeg = await run_in_threadpool(to_jpeg, thumb.data, thumb.content_type)
        # JPEG eklenince maliyet arttı; önbellek hesabını tazele.
        _cache.put(cache_key(item.url), thumb)
    return thumb.jpeg
