import {
  motion,
  useScroll,
  useTransform,
  useSpring,
  type MotionValue,
} from 'framer-motion'
import { useRef, type ReactNode, type CSSProperties } from 'react'
import { REDUCED_MOTION } from '@/lib/motion'

interface ParallaxProps {
  children: ReactNode
  /** Parallax speed: positive = moves slower than scroll, negative = faster. Range: -0.5 to 0.5 recommended */
  speed?: number
  className?: string
  style?: CSSProperties
  as?: 'div' | 'section'
}

export function Parallax({
  children,
  speed = 0.15,
  className,
  style,
  as = 'div',
}: ParallaxProps) {
  const ref = useRef<HTMLDivElement>(null)

  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  })

  const rawY = useTransform(scrollYProgress, [0, 1], [speed * 100, speed * -100])
  const y = useSpring(rawY, { stiffness: 200, damping: 30 }) as MotionValue<number>

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
    <Component ref={ref} className={className} style={{ ...style, y }}>
      {children}
    </Component>
  )
}
