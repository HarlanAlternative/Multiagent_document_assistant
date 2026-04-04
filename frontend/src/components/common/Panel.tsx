import type { PropsWithChildren, ReactNode } from "react";

type PanelProps = PropsWithChildren<{
  title?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}>;

export function Panel({ title, description, actions, className = "", children }: PanelProps) {
  return (
    <section className={`rounded-3xl border border-white/70 bg-white/90 p-6 shadow-panel ${className}`}>
      {(title || description || actions) && (
        <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            {title ? <h2 className="text-lg font-semibold text-ink-900">{title}</h2> : null}
            {description ? <p className="mt-1 text-sm text-ink-600">{description}</p> : null}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}
