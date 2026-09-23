const bar = 'rounded-[8px] bg-surface-2';

/**
 * "Henüz bir bağlantı yok" kutusuyla aynı ölçüde iskelet. İçerideki bloklar
 * yüklenmiş ekranın kaba hâli: solda kapak + başlık, sağda sekme + kalite satırları.
 */
export default function LoadingState() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mt-v32 flex min-h-[280px] flex-col justify-center rounded-[22px] border border-dashed border-line bg-surface/60 px-6 py-[var(--p-empty)] md:min-h-[var(--h-empty)] md:px-10"
    >
      <span className="sr-only">Bağlantı çözümleniyor…</span>

      <div aria-hidden="true" className="grid animate-pulse grid-cols-1 gap-v24 md:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] md:gap-v40">
        <div>
          <div className={'aspect-video w-full rounded-card bg-surface-2'} />
          <div className={bar + ' mt-v16 h-4 w-4/5'} />
          <div className={bar + ' mt-v10 h-3.5 w-2/5'} />
        </div>

        <div className="hidden md:block">
          <div className="h-[52px] rounded-[16px] bg-surface-2" />
          <div className="mt-v24 overflow-hidden rounded-card border border-line-soft">
            {[0, 1, 2].map((row) => (
              <div key={row} className="flex h-[var(--h-row)] items-center justify-between border-b border-line-soft px-[18px] last:border-b-0">
                <div className={bar + ' h-3.5 w-16'} />
                <div className={bar + ' h-3 w-12'} />
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-v20 text-center text-[13.5px] font-semibold text-muted">Bağlantı çözümleniyor — kapak ve kalite seçenekleri alınıyor</p>
    </div>
  );
}
