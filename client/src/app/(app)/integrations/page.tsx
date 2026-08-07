"use client"

import { Check, Github, RefreshCw, Unplug, Layers } from 'lucide-react'
import { PageHeader } from '@/components/PageHeader'
import { integrations } from '@/lib/demo'
import { Reveal } from '@/components/motion/Reveal'
import { Stagger, StaggerItem } from '@/components/motion/Stagger'

export default function Integrations() {
  return (
    <div className="container-normal py-10 pb-24 md:py-12">
      <PageHeader 
        eyebrow="Connected evidence" 
        title="Integrations" 
        description="External signals remain inferred until you explicitly add them to your skill bank."
      />
      
      <div className="mt-10">
        <Stagger className="grid gap-6 lg:grid-cols-2" staggerDelay={0.05}>
          {integrations.map(item => (
            <StaggerItem as="article" key={item.provider} className="flex flex-col overflow-hidden rounded-xl border bg-surface shadow-sm transition-colors hover:border-line hover:bg-raised">
              {/* Header section */}
              <div className="flex flex-col gap-6 p-6 sm:p-8">
                <div className="flex items-start justify-between">
                  <div className="grid size-12 shrink-0 place-items-center rounded-full border bg-canvas shadow-sm">
                    {item.provider === 'github' ? <Github size={22} className="text-ink" /> : <span className="font-mono text-sm font-bold">LC</span>}
                  </div>
                  {item.connected ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-success/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-success">
                      <div className="size-1.5 rounded-full bg-success" />
                      Connected
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-muted">
                      Disconnected
                    </span>
                  )}
                </div>
                
                <div>
                  <h2 className="font-display text-2xl font-medium capitalize">{item.provider}</h2>
                  <p className="mt-2 text-sm leading-relaxed text-muted">
                    {item.connected ? (
                      <span className="font-mono bg-canvas px-1.5 py-0.5 rounded border mr-2 text-xs text-ink">{item.handle}</span>
                    ) : (
                      'Connect your profile to surface evidence-backed topic strengths and automatically index public commits.'
                    )}
                  </p>
                  
                  {item.connected && (
                    <p className="mt-3 text-[11px] font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
                      <RefreshCw size={12} />
                      Synced {item.lastSyncedAt}
                    </p>
                  )}
                </div>
                
                <div className="mt-auto flex flex-wrap gap-3 pt-2">
                  {item.connected ? (
                    <>
                      <button className="button-secondary">
                        <RefreshCw size={15} />
                        Sync now
                      </button>
                      <button className="button-ghost hover:!bg-danger/10 hover:text-danger">
                        <Unplug size={15} />
                        Disconnect
                      </button>
                    </>
                  ) : (
                    <button className="button-primary">
                      Connect {item.provider}
                    </button>
                  )}
                </div>
              </div>

              {/* Inferred items section */}
              <div className="flex-1 border-t bg-raised/40 p-6 sm:p-8">
                {item.connected ? (
                  <>
                    <div className="mb-5 flex items-center justify-between">
                      <p className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-2">
                        <Layers size={14} />
                        Last sync findings
                      </p>
                      <span className="tag !border-warning/40 !bg-warning/10 !text-warning-dark !px-2 !py-0.5 !text-[10px]">Inferred — not claimed</span>
                    </div>
                    <div className="divide-y border-y bg-canvas/50">
                      {item.inferredSkills.map(skill => (
                        <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between" key={skill.id}>
                          <div>
                            <p className="font-medium text-ink">{skill.name}</p>
                            <p className="mt-1 text-xs text-muted">Inferred from {item.provider} activity</p>
                          </div>
                          <button className="button-secondary !py-1.5 shrink-0 text-xs">
                            <Check size={14} />
                            Review & add
                          </button>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="flex h-full min-h-32 flex-col items-center justify-center text-center">
                    <p className="text-sm font-medium text-ink">Nothing is imported automatically.</p>
                    <p className="mt-2 max-w-xs text-sm text-muted">After syncing, each inferred skill appears here for review.</p>
                  </div>
                )}
              </div>
            </StaggerItem>
          ))}
        </Stagger>
      </div>
    </div>
  )
}
