import { ArrowUpRightIcon } from './Icons';

export default function Footer() {
  return (
    <footer className="mt-v40 flex items-center justify-center border-t border-line-soft py-v20">
      <p className="text-[12.5px] font-medium text-muted">
        <a
          href="https://asilturkmen.com"
          target="_blank"
          rel="noopener"
          title="Asil Türkmen — kişisel site"
          className="group inline-flex items-center gap-[3px] font-bold text-ink underline decoration-accent/35 decoration-2 underline-offset-[4px] transition-colors hover:text-accent hover:decoration-accent"
        >
          asilturkmen.com
          <ArrowUpRightIcon className="h-[12px] w-[12px] text-accent transition-transform duration-200 group-hover:-translate-y-[1.5px] group-hover:translate-x-[1.5px]" />
        </a>{' '}
        tarafından geliştirildi
      </p>
    </footer>
  );
}
