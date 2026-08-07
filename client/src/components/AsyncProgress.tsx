import { AlertTriangle, CheckCircle2, LoaderCircle } from 'lucide-react'
import type { JobState } from '@/lib/types'
import { motion } from 'framer-motion'

interface AsyncProgressProps {
  state: JobState
  progress: number
  stage: string
}

export function AsyncProgress({ state, progress, stage }: AsyncProgressProps) {
  const done = state === 'done'
  const failed = state === 'failed'

  return (
    <div
      className="border-y bg-surface/50 px-5 py-5 shadow-sm md:rounded-lg md:border-x"
      role="status"
      aria-live="polite"
    >
      <div className="mb-4 flex items-center justify-between gap-4 text-sm">
        <div className="flex items-center gap-3 font-semibold">
          {done ? (
            <CheckCircle2 className="text-success" size={18} />
          ) : failed ? (
            <AlertTriangle className="text-danger" size={18} />
          ) : (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
            >
              <LoaderCircle className="text-accent" size={18} />
            </motion.div>
          )}
          <span>{stage}</span>
        </div>
        <span className="font-mono text-xs font-bold text-muted">{progress}%</span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-line/60">
        <motion.div
          className={`h-full origin-left ${
            failed ? 'bg-danger' : done ? 'bg-success' : 'bg-accent'
          }`}
          initial={{ scaleX: 0 }}
          animate={{ scaleX: progress / 100 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}
