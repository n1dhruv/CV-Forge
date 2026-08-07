import type { Variants, Transition } from 'framer-motion'

// ── Timing ──────────────────────────────────────────────────────────
export const DURATION = {
  micro: 0.15,
  fast: 0.25,
  normal: 0.35,
  section: 0.55,
  slow: 0.75,
} as const

// ── Easing ──────────────────────────────────────────────────────────
export const EASE = {
  outExpo: [0.16, 1, 0.3, 1] as [number, number, number, number],
  outQuart: [0.25, 1, 0.5, 1] as [number, number, number, number],
  inOutCubic: [0.65, 0, 0.35, 1] as [number, number, number, number],
} as const

// ── Spring presets ──────────────────────────────────────────────────
export const SPRING = {
  snappy: { type: 'spring' as const, stiffness: 400, damping: 30 },
  gentle: { type: 'spring' as const, stiffness: 200, damping: 24 },
  bouncy: { type: 'spring' as const, stiffness: 300, damping: 20 },
} as const

// ── Transition presets ──────────────────────────────────────────────
export const TRANSITION: Record<string, Transition> = {
  micro: { duration: DURATION.micro, ease: EASE.outExpo },
  normal: { duration: DURATION.normal, ease: EASE.outExpo },
  section: { duration: DURATION.section, ease: EASE.outExpo },
  slow: { duration: DURATION.slow, ease: EASE.outQuart },
}

// ── Reusable variants ───────────────────────────────────────────────

/** Fade in with subtle upward movement */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.section, ease: EASE.outExpo },
  },
}

/** Fade in with subtle downward movement */
export const fadeInDown: Variants = {
  hidden: { opacity: 0, y: -16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: DURATION.section, ease: EASE.outExpo },
  },
}

/** Simple opacity fade */
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { duration: DURATION.normal, ease: EASE.outExpo },
  },
}

/** Scale in from slightly smaller */
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: {
    opacity: 1,
    scale: 1,
    transition: { duration: DURATION.section, ease: EASE.outExpo },
  },
}

/** Stagger container — orchestrates child animations */
export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.1,
    },
  },
}

/** Stagger with longer delay for section-level reveals */
export const staggerSlow: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.15,
    },
  },
}

// ── Media queries ───────────────────────────────────────────────────
export const REDUCED_MOTION =
  typeof window !== 'undefined'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false
