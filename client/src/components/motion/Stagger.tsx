import { motion, useInView } from 'framer-motion'
import { useRef, type ReactNode, type CSSProperties } from 'react'
import { staggerContainer, fadeInUp, REDUCED_MOTION } from '@/lib/motion'

interface StaggerProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** Delay between each child animation in seconds */
  staggerDelay?: number
  /** Initial delay before the first child animates */
  initialDelay?: number
  /** Intersection threshold to trigger */
  threshold?: number
  as?: 'div' | 'ul' | 'ol' | 'section'
}

export function Stagger({
  children,
  className,
  style,
  staggerDelay = 0.08,
  initialDelay = 0.1,
  threshold = 0.1,
  as = 'div',
}: StaggerProps) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: threshold })

  if (REDUCED_MOTION) {
    const Tag = as
    return (
      <Tag className={className} style={style}>
        {children}
      </Tag>
    )
  }

  const Component = motion[as] as typeof motion.div

  return (
    <Component
      ref={ref}
      className={className}
      style={style}
      initial="hidden"
      animate={inView ? 'visible' : 'hidden'}
      variants={{
        hidden: {},
        visible: {
          transition: {
            staggerChildren: staggerDelay,
            delayChildren: initialDelay,
          },
        },
      }}
    >
      {children}
    </Component>
  )
}

/** Wrap each stagger child in this to receive the animation */
export function StaggerItem({
  children,
  className,
  style,
  as = 'div',
}: {
  children: ReactNode
  className?: string
  style?: CSSProperties
  as?: 'div' | 'li' | 'article' | 'section'
}) {
  if (REDUCED_MOTION) {
    const Tag = as
    return (
      <Tag className={className} style={style}>
        {children}
      </Tag>
    )
  }

  const Component = motion[as] as typeof motion.div

  return (
    <Component className={className} style={style} variants={fadeInUp}>
      {children}
    </Component>
  )
}
