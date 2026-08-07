import type { ReactNode } from 'react'
import { Reveal } from './motion/Reveal'

interface PageHeaderProps {
  eyebrow: string
  title: string
  description?: string
  action?: ReactNode
}

export function PageHeader({ eyebrow, title, description, action }: PageHeaderProps) {
  return (
    <Reveal variant="down" as="header" className="mb-12 flex flex-col justify-between gap-6 border-b pb-8 md:flex-row md:items-end">
      <div>
        <p className="eyebrow mb-4">{eyebrow}</p>
        <h1 className="page-title">{title}</h1>
        {description && <p className="mt-4 max-w-2xl text-muted">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </Reveal>
  )
}
