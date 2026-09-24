"""Sunucuyu .env ayarlarıyla başlatır:  python serve.py

`uvicorn app:app --port 8000` da çalışır; bu dosya, ayarları tek yerden
(.env) almak ve iki kuralı zorunlu kılmak için var:

  - Tek worker. Önbellek, IP sınırları, indirme biletleri ve relay süreç
    içinde, bellekte tutuluyor; birden fazla worker'da prepare bir sürece,
    download başka bir sürece düşer. Tek süreç yeterli: iş asenkron, ağır
    kısımlar (yt-dlp, ffmpeg) thread'lerde ve ayrı süreçlerde çalışıyor.
    Daha fazla kapasite için birden çok örnek + nginx `ip_hash` (her
    istemci hep aynı örneğe gider).
  - X-Forwarded-For yalnızca FORWARDED_ALLOW_IPS'teki proxy'lerden kabul edilir.
  - Kapanış süresi sınırlı. uvicorn varsayılan olarak açık bağlantıların
    bitmesini sonsuza kadar bekler; süren bir indirme `systemctl restart`'ı
    dakikalarca tutardı. Süre dolunca kalan indirmeler kesilir (istemci yarım
    dosyayı hata olarak görür) ve ffmpeg süreçleri kapatılır.
"""

import uvicorn

import config

if __name__ == '__main__':
    uvicorn.run(
        'app:app',
        host=config.HOST,
        port=config.PORT,
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=config.FORWARDED_ALLOW_IPS,
        timeout_graceful_shutdown=config.SHUTDOWN_TIMEOUT_SECONDS,
    )
