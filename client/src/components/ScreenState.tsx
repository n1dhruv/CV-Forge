import { AlertTriangle, Inbox, RotateCw } from 'lucide-react'
import { Reveal } from './motion/Reveal'
import { motion } from 'framer-motion'

interface ScreenStateProps {
  kind: 'loading' | 'empty' | 'error'
  title: string
  detail: string
  onRetry?: () => void
}

export function ScreenState({ kind, title, detail, onRetry }: ScreenStateProps) {
  return (
    <Reveal variant="scale" className="grid min-h-64 place-items-center border-y bg-surface/30 py-16 text-center">
      <div className="max-w-sm" role={kind === 'error' ? 'alert' : 'status'} aria-live="polite">
        {kind === 'loading' ? (
          <div className="mx-auto mb-12 size-20 relative flex items-center justify-center">
            {/* Steam */}
            <div className="absolute top-0 inset-x-0 flex justify-center gap-3 z-0">
              {[0, 1, 2].map(i => (
                <motion.div
                  key={i}
                  className="w-1.5 h-5 bg-accent/60 rounded-full blur-[1px]"
                  animate={{ y: [10, -15], opacity: [0, 1, 0], scaleY: [0.8, 1.2, 0.8] }}
                  transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.4, ease: "easeInOut" }}
                />
              ))}
            </div>
            
            {/* The Pot Body */}
            <div className="absolute bottom-2 w-16 h-10 bg-surface border-2 border-ink rounded-b-2xl rounded-t-sm z-10 overflow-hidden shadow-md">
               {/* Bubbling liquid inside */}
               <motion.div 
                 className="absolute inset-x-0 bottom-0 bg-accent-soft border-t-2 border-accent"
                 animate={{ height: ['40%', '70%', '40%'] }}
                 transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
               />
               {/* Floating bubbles */}
               {[0, 1, 2, 3].map(i => (
                 <motion.div
                   key={`bubble-${i}`}
                   className="absolute size-2 bg-accent rounded-full"
                   style={{ left: `${15 + i * 20}%` }}
                   animate={{ bottom: ['0%', '100%'], opacity: [1, 0], scale: [0.5, 1.5] }}
                   transition={{ duration: 0.8 + (i * 0.2), repeat: Infinity, delay: i * 0.2, ease: 'easeOut' }}
                 />
               ))}
            </div>
            
            {/* Pot handles */}
            <div className="absolute bottom-5 -left-1.5 w-2 h-4 border-2 border-ink rounded-l-md border-r-0 z-0" />
            <div className="absolute bottom-5 -right-1.5 w-2 h-4 border-2 border-ink rounded-r-md border-l-0 z-0" />
            
            {/* Bouncing Lid */}
            <motion.div 
              className="absolute bottom-[44px] w-[72px] flex flex-col items-center z-20"
              animate={{ y: [0, -6, 0], rotate: [0, 3, -2, 0] }}
              transition={{ duration: 0.5, repeat: Infinity, ease: 'easeOut' }}
            >
               <div className="w-5 h-2.5 border-2 border-ink border-b-0 rounded-t-md" />
               <div className="w-full h-1.5 bg-ink rounded-full" />
            </motion.div>
          </div>
        ) : kind === 'error' ? (
          <div className="mx-auto mb-6 grid size-12 place-items-center rounded-full bg-danger/10 text-danger">
            <AlertTriangle size={24} aria-hidden="true" />
          </div>
        ) : (
          <div className="mx-auto mb-6 grid size-12 place-items-center rounded-full bg-surface text-muted shadow-sm">
            <Inbox size={24} aria-hidden="true" />
          </div>
        )}

        <h2 className="section-title text-xl">{title}</h2>
        <p className="mt-3 text-sm leading-relaxed text-muted">{detail}</p>

        {onRetry && (
          <button onClick={onRetry} className="button-secondary mt-6">
            <RotateCw size={16} aria-hidden="true" />
            Try Again
          </button>
        )}
      </div>
    </Reveal>
  )
}
