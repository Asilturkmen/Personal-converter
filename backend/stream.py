"""ffmpeg: CDN'den okur, stdout'a yazar. Diske hiçbir şey dokunmaz.

Neden asyncio.create_subprocess_exec değil de subprocess.Popen?
  Windows'ta uvicorn (özellikle --reload ile) SelectorEventLoop kullanır ve
  asyncio'nun alt süreç API'si orada NotImplementedError fırlatır. Popen her
  olay döngüsünde ve her platformda çalışır; bloklayan stdout okumaları
  anyio'nun thread havuzunda yapılır, event loop hiç bloklanmaz.
"""

from __future__ import annotations

import collections
import logging
import subprocess
import threading
import time
from dataclasses import dataclass

import config
from media import Choice, Stream

log = logging.getLogger('converter.stream')

CHUNK_SIZE = 64 * 1024

# Kaynak koparsa yeniden bağlan, ama sonsuza kadar değil: aksi hâlde ölü bir
# kaynak indirmeyi zaman aşımına kadar asılı tutar.
# rw_timeout: 30 sn hiç veri gelmezse G/Ç hatası (mikrosaniye).
IO_TIMEOUT = ['-rw_timeout', '30000000']
RECONNECT = ['-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '5',
             '-reconnect_max_retries', '5', *IO_TIMEOUT]

# ffmpeg yarıda kesilen bir girdiyi bu mesajlarla bildirip yine de 0 ile
# çıkabiliyor (ölçüldü: %40'ı verilmiş girdi → "partial file", çıkış kodu 0).
# -loglevel error altında görünen bu satırlar kesinti sayılır.
TRUNCATION_MARKERS = ('partial file', 'prematurely', 'i/o error', 'connection reset', 'error during demuxing')
# -map ile istenen akış girdide yok (ör. sessiz video → MP3). Yeniden denemek
# sonucu değiştirmez.
MISSING_STREAM_MARKER = 'matches no streams'
FRAGMENTED_MP4 = ['-movflags', 'frag_keyframe+empty_moov+default_base_moof', '-f', 'mp4']


class StreamFailed(Exception):
    """Akış yarıda kesildi. Yanıt gövdesi temiz kapanmasın diye yükseltilir;
    istemci böylece yarım dosyayı başarılı saymaz."""


def _input_args(stream: Stream, relay_url: str | None) -> list[str]:
    if relay_url:
        # Loopback köprüsü: CDN başlıkları ve yeniden deneme relay.py'de.
        return [*IO_TIMEOUT, '-i', relay_url]
    args = list(RECONNECT)
    if stream.headers:
        # ffmpeg her başlığın CRLF ile bitmesini bekliyor.
        joined = ''.join(f'{key}: {value}\r\n' for key, value in stream.headers.items())
        args += ['-headers', joined]
    return args + ['-i', stream.url]


def build_command(choice: Choice, *, relay_urls: list[str | None] | None = None) -> list[str]:
    """relay_urls[i] doluysa i. girdi CDN yerine o adresten okunur."""
    relays = relay_urls or [None] * len(choice.inputs)
    cmd = [config.FFMPEG_PATH, '-hide_banner', '-loglevel', 'error', '-nostats']

    if choice.kind == 'video':
        cmd.append('-nostdin')
        for stream, relay_url in zip(choice.inputs, relays):
            cmd += _input_args(stream, relay_url)
        if len(choice.inputs) == 2:
            cmd += ['-map', '0:v:0', '-map', '1:a:0']
        else:
            # Instagram çoğunlukla tek parça: video+ses aynı akışta.
            cmd += ['-map', '0:v:0', '-map', '0:a:0?']
        # Yeniden kodlama yok: yalnızca kapsayıcı değişiyor.
        cmd += ['-c', 'copy']
        if choice.inputs[-1].hls_aac:
            cmd += ['-bsf:a', 'aac_adtstoasc']
        return cmd + FRAGMENTED_MP4 + ['pipe:1']

    # MP3: etiketsiz ham akış. ID3 etiketi (başlık, sanatçı, kapak) tags.py'de
    # bellekte üretilip akışın başına eklenir; ffmpeg pipe'a yazarken etiket
    # boyutunu dolduramıyor.
    cmd.append('-nostdin')
    cmd += _input_args(choice.inputs[0], relays[0])
    cmd += ['-map', '0:a:0', '-vn', '-map_metadata', '-1']
    # Sabit bit hızı (varsayılan 192 kbps). VBR'nin süre başlığı (Xing) dosya
    # bitince geriye dönülerek yazılır; pipe'ta bu mümkün değil ve oynatıcılar
    # süreyi yanlış gösterir. CBR'de süre ve konum bit hızından tam hesaplanır.
    # Kaynak ~130 kbps opus/AAC olduğu için daha yüksek bit hızı kalite katmaz.
    return cmd + ['-c:a', 'libmp3lame', '-b:a', f'{config.MP3_BITRATE_KBPS}k',
                  '-write_id3v2', '0', '-write_xing', '0', '-f', 'mp3', 'pipe:1']


@dataclass
class _Tail:
    """ffmpeg stderr'inin son satırları; hata olursa log'a basılır."""
    lines: collections.deque

    def text(self) -> str:
        return ' | '.join(self.lines)


WATCH_INTERVAL = 5


def time_limit(estimated_bytes: int) -> float:
    """Üst süre: en az DOWNLOAD_TIMEOUT, büyük dosyada en düşük kabul edilen
    hızla inmesine yetecek kadar. Sabit bir süre yavaş bağlantıda büyük
    dosyayı yarıda keserdi (1 GB, 15 dk → 1,1 MB/sn altı hep başarısız)."""
    return max(config.DOWNLOAD_TIMEOUT_SECONDS, estimated_bytes / config.MIN_DOWNLOAD_BYTES_PER_SECOND)


class FFmpegStream:
    def __init__(self, cmd: list[str], *, max_seconds: float | None = None):
        self.cmd = cmd
        self.max_seconds = max_seconds or config.DOWNLOAD_TIMEOUT_SECONDS
        self.proc: subprocess.Popen | None = None
        self.bytes_sent = 0
        self.started_at = time.monotonic()
        self._last_data = self.started_at
        self._stderr = _Tail(collections.deque(maxlen=20))
        self._killed_reason: str | None = None
        self._closed = threading.Event()
        self._watchdog: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None

    def start(self) -> None:
        self.proc = subprocess.Popen(
            self.cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

        self.started_at = self._last_data = time.monotonic()
        self._watchdog = threading.Thread(target=self._watch, daemon=True)
        self._watchdog.start()

    def _watch(self) -> None:
        """Süre aşılırsa ya da akış durursa süreç öldürülür; okuma döngüsü de
        EOF alıp çıkar. İlerleyen bir indirme yalnızca üst süreye takılır."""
        while not self._closed.wait(WATCH_INTERVAL):
            now = time.monotonic()
            if now - self.started_at > self.max_seconds:
                self.kill('zaman aşımı')
                return
            if now - self._last_data > config.DOWNLOAD_STALL_SECONDS:
                self.kill(f'akış {config.DOWNLOAD_STALL_SECONDS} sn durdu')
                return

    def _drain_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for raw in self.proc.stderr:
            line = raw.decode('utf-8', 'replace').strip()
            if line:
                self._stderr.lines.append(line)

    def read(self) -> bytes:
        """Bloklayan okuma; thread havuzunda çağrılır. b'' = akış bitti."""
        assert self.proc and self.proc.stdout
        try:
            chunk = self.proc.stdout.read(CHUNK_SIZE)
        except (OSError, ValueError):
            return b''
        if chunk:
            # İstemci okumayı bırakırsa ffmpeg pipe'ta bekler, buraya da veri
            # gelmez: yavaş kaynak da, okumayan istemci de "durma" sayılır.
            self._last_data = time.monotonic()
            self.bytes_sent += len(chunk)
            if self.bytes_sent > config.MAX_BYTES:
                self.kill('boyut sınırı aşıldı')
        return chunk or b''

    def kill(self, reason: str = 'iptal') -> None:
        if self.proc and self.proc.poll() is None:
            self._killed_reason = self._killed_reason or reason
            try:
                # Her iki platformda çalışır; platforma özel sinyal yok.
                self.proc.kill()
            except OSError:
                pass

    def finish(self) -> None:
        """Akış sonunda çağrılır: çıkış kodunu kontrol eder, başarısızsa
        StreamFailed yükseltir."""
        assert self.proc
        try:
            code = self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.kill('kapanmadı')
            code = self.proc.wait()
        # stderr'in son satırları okunmadan karar verilmesin.
        if self._stderr_thread:
            self._stderr_thread.join(timeout=5)
        stderr = self._stderr.text().lower()
        truncated = next((marker for marker in TRUNCATION_MARKERS if marker in stderr), None)
        if self._killed_reason or code != 0 or truncated:
            reason = self._killed_reason or (f'girdi eksik ({truncated})' if truncated else f'ffmpeg çıkış kodu {code}')
            log.warning('akış başarısız (%s, %d bayt): %s', reason, self.bytes_sent, self._stderr.text())
            raise StreamFailed(reason)

    def close(self) -> None:
        """Her durumda (istemci koptu, hata, başarı) çağrılır."""
        self._closed.set()
        self.kill('istemci bağlantıyı kapattı')
        if self.proc:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            for pipe in (self.proc.stdout, self.proc.stderr):
                try:
                    pipe and pipe.close()
                except OSError:
                    pass

    def startup_error(self) -> str:
        """İlk bayt gelmediyse çağrılır (bloklar, thread havuzunda): süreci
        durdurur ve stderr'in sonuna kadar okunmasını bekler. Aksi hâlde
        ffmpeg'in son satırı henüz okunmamış olabilir."""
        self.kill('başlamadı')
        if self.proc:
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        if self._stderr_thread:
            self._stderr_thread.join(timeout=2)
        return self._stderr.text()
