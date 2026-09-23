"""MP3 etiketleri, bellekte.

ffmpeg'in mp3 muxer'ı ID3v2 etiketinin boyutunu dosyanın sonunda geri dönüp
yazar. Akışa (pipe) yazarken geri dönemediği için boyut 0 kalır; oynatıcılar
da etiketi görmez, kapak ve başlık kaybolur, etiketin baytları ses sanılır.

Bu yüzden ffmpeg etiketsiz ham MP3 üretir (-write_id3v2 0) ve etiket burada
mutagen ile oluşturulup akışın başına eklenir. Hiçbir şey diske yazılmaz.
"""

from __future__ import annotations

import logging
import subprocess
from io import BytesIO

from mutagen.id3 import APIC, ID3, TIT2, TPE1

import config

log = logging.getLogger('converter.tags')


def to_jpeg(data: bytes, content_type: str) -> bytes | None:
    """YouTube kapakları çoğu zaman WebP; ID3 kapağında JPEG en uyumlusu.
    Dönüşüm ffmpeg ile stdin → stdout, bellekte yapılır."""
    if content_type == 'image/jpeg':
        return data
    try:
        result = subprocess.run(
            [config.FFMPEG_PATH, '-v', 'error', '-i', 'pipe:0', '-frames:v', '1',
             '-c:v', 'mjpeg', '-q:v', '2', '-f', 'image2pipe', 'pipe:1'],
            input=data,
            capture_output=True,
            timeout=15,
        )
    except (subprocess.SubprocessError, OSError) as error:
        log.info('kapak JPEG\'e çevrilemedi: %s', error)
        return None
    return result.stdout if result.returncode == 0 and result.stdout else None


def id3_tag(*, title: str | None, artist: str | None, cover: bytes | None) -> bytes:
    tag = ID3()
    if title:
        tag.add(TIT2(encoding=3, text=title))
    if artist:
        tag.add(TPE1(encoding=3, text=artist))
    if cover:
        tag.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover))
    if not tag:
        return b''
    buffer = BytesIO()
    # v2.3: Windows Gezgini ve eski oynatıcılar v2.4'ü tam okumuyor.
    tag.save(buffer, v2_version=3, v1=0, padding=lambda info: 0)
    return buffer.getvalue()
