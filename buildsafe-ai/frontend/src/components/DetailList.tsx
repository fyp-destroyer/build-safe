interface DetailListProps {
  title: string;
  items: string[];
  emptyLabel?: string;
}

export function DetailList({ title, items, emptyLabel = "None listed" }: DetailListProps): JSX.Element {
  return (
    <section className="min-w-0">
      <h3 className="text-sm font-semibold uppercase tracking-[0.08em] text-zinc-500">{title}</h3>
      {items.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item} className="rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-700">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 rounded-md border border-zinc-200 bg-white px-3 py-2 text-sm text-zinc-500">
          {emptyLabel}
        </p>
      )}
    </section>
  );
}
