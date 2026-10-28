export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-card px-6 py-10">
      <h2 className="font-serif text-2xl">{title}</h2>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{body}</p>
    </div>
  )
}
