import { VideoIcon } from './Icons';

export default function EmptyState() {
  return (
    <div className="mt-v32 flex min-h-[280px] flex-col items-center justify-center gap-v18 rounded-[22px] border border-dashed border-line bg-surface/60 px-6 py-[clamp(20px,3.69vh,48px)] md:min-h-[clamp(200px,30.77vh,400px)]">
      <span className="flex h-[74px] w-[74px] items-center justify-center rounded-[22px] border border-line bg-surface text-muted">
        <VideoIcon className="h-[30px] w-[30px]" />
      </span>

      <div className="flex flex-col items-center gap-2">
        <span className="text-xl font-bold tracking-[-0.015em]">Henüz bir bağlantı yok</span>
        <span className="max-w-[420px] text-center text-[15px] font-medium leading-relaxed text-muted">
          Bir bağlantı yapıştırdığında videonun kapağı, süresi ve tüm kalite seçenekleri burada belirir.
        </span>
      </div>
    </div>
  );
}
