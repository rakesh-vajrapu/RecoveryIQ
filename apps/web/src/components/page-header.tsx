import type { LucideIcon } from "lucide-react";

export function PageHeader({ eyebrow, title, description, icon: Icon, actions }: { eyebrow: string; title: string; description: string; icon?: LucideIcon; actions?: React.ReactNode }) {
  return (
    <section className="mb-7 flex flex-col justify-between gap-5 sm:mb-9 xl:flex-row xl:items-end">
      <div className="max-w-3xl">
        <div className="mb-3 flex items-center gap-2">{Icon && <Icon className="size-3.5 text-primary" />}<p className="eyebrow text-primary">{eyebrow}</p></div>
        <h1 className="gradient-text text-3xl font-bold tracking-[-0.035em] sm:text-4xl">{title}</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-[15px]">{description}</p>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </section>
  );
}

