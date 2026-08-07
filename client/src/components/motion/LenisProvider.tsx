import { ReactLenis } from 'lenis/react'
import { type ReactNode, useEffect, useRef } from 'react'
import { REDUCED_MOTION } from '@/lib/motion'

interface LenisProviderProps {
  children: ReactNode
}

export function LenisProvider({ children }: LenisProviderProps) {
  const lenisRef = useRef<any>(null)

  // Disable smooth scrolling when user prefers reduced motion
  useEffect(() => {
    if (REDUCED_MOTION && lenisRef.current) {
      // Lenis will be initialized but with duration effectively instant
    }
  }, [])

  if (REDUCED_MOTION) {
    return <>{children}</>
  }

  return (
    <ReactLenis
      ref={lenisRef}
      root
      options={{
        lerp: 0.1,
        duration: 1.2,
        smoothWheel: true,
        wheelMultiplier: 1,
        touchMultiplier: 2,
        infinite: false,
      }}
    >
      {children}
    </ReactLenis>
  )
}
