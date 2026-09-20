interface Props {
  message: string;
}

export default function ErrorNote({ message }: Props) {
  return (
    <p role="alert" className="mt-4 rounded-control border border-line bg-surface px-4 py-3 text-sm font-semibold text-ink">
      {message}
    </p>
  );
}
