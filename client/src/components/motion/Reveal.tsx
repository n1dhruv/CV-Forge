import { motion, useInView } from 'framer-motion'
import { useRef, type ReactNode, type CSSProperties } from 'react'
import { fadeInUp, fadeInDown, fadeIn, scaleIn, REDUCED_MOTION } from '@/lib/motion'

type RevealVariant = 'up' | 'down' | 'fade' | 'scale'

interface RevealProps {
  children: ReactNode
  variant?: RevealVariant
  delay?: number
  className?: string
  style?: CSSProperties
  /** How much of the element must be visible to trigger (0-1) */
  threshold?: number
  /** Only animate once */
  once?: boolean
  as?: 'div' | 'section' | 'article' | 'header' | 'footer' | 'aside' | 'li'
}

const variantMap = {
  up: fadeInUp,
  down: fadeInDown,
  fade: fadeIn,
  scale: scaleIn,
}

export function Reveal({
  children,
  variant = 'up',
  delay = 0,
  className,
  style,
  threshold = 0.15,
  once = true,
  as = 'div',
}: RevealProps) {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once, amount: threshold })

  // Skip animation entirely if reduced motion is preferred
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
      variants={variantMap[variant]}
      transition={{ delay }}
    >
      {children}
    </Component>
  )
}
