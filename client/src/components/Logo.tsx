import { motion } from 'framer-motion'
import { REDUCED_MOTION, DURATION, EASE } from '@/lib/motion'

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <motion.span
        aria-hidden
        className="grid size-7 place-items-center border border-ink font-display text-lg leading-none"
        whileHover={
          REDUCED_MOTION
            ? {}
            : { scale: 1.08, rotate: -2 }
        }
        transition={{ duration: DURATION.micro, ease: EASE.outExpo }}
      >
        R
      </motion.span>
      <span className="font-display text-xl font-semibold tracking-tight">
        MakeMyResume
      </span>
    </div>
  )
}
