export function PageHeader({
  title,
  description,
  phase = 'Phase 0',
}: {
  title: string
  description: string
  phase?: string
}) {
  return (
    <header className="mb-8">
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-primary">{phase}</p>
      <h1 className="mt-2 font-serif text-4xl tracking-tight">{title}</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">{description}</p>
    </header>
  )
}
