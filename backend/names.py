"""Dosya adları: Windows'ta yasak karakterler temizlenir, Türkçe korunur."""

import re
import unicodedata
from urllib.parse import quote

FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
ASCII_MAP = str.maketrans({'ı': 'i', 'İ': 'I', 'ş': 's', 'Ş': 'S', 'ğ': 'g', 'Ğ': 'G'})


def safe_filename(title: str, ext: str, limit: int = 150) -> str:
    name = FORBIDDEN.sub(' ', title or '')
    name = re.sub(r'\s+', ' ', name).strip(' .')
    name = name[:limit].rstrip(' .')
    if not name:
        name = 'video'
    if name.split('.')[0].upper() in RESERVED:
        name = '_' + name
    return f'{name}.{ext}'


def content_disposition(filename: str) -> str:
    """RFC 6266 + RFC 5987: eski istemciler için ASCII yedek, diğerleri için
    UTF-8 ile kodlanmış asıl ad."""
    fallback = unicodedata.normalize('NFKD', filename.translate(ASCII_MAP))
    fallback = fallback.encode('ascii', 'ignore').decode('ascii').replace('"', '').replace('\\', '')
    if not fallback.strip(' .'):
        fallback = 'video' + filename[filename.rfind('.'):]
    return f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}'
