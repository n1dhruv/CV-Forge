"use client"

import { Minus, Plus } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import type { PDFDocumentProxy, PDFPageProxy, RenderTask } from 'pdfjs-dist'
import { nextPdfZoom } from '@/lib/resume-editor'

interface PdfPreviewProps {
  url: string
  stale?: boolean
}

export default function PdfPreview({ url, stale = false }: PdfPreviewProps) {
  const [document, setDocument] = useState<PDFDocumentProxy>()
  const [zoom, setZoom] = useState(100)
  const [error, setError] = useState<string>()

  useEffect(() => {
    let active = true
    let loaded: PDFDocumentProxy | undefined
    setDocument(undefined)
    setError(undefined)
    void import('pdfjs-dist').then(pdfjs => {
      pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        'pdfjs-dist/build/pdf.worker.min.mjs',
        import.meta.url,
      ).toString()
      return pdfjs.getDocument({ url }).promise
    }).then(pdf => {
      loaded = pdf
      if (active) setDocument(pdf)
    }).catch(() => {
      if (active) setError('The PDF could not be rendered.')
    })
    return () => {
      active = false
      void loaded?.cleanup()
    }
  }, [url])

  return (
    <div className="flex size-full min-h-0 flex-col bg-[#2d2d2d]">
      <div className="no-print flex min-h-12 shrink-0 items-center justify-center gap-1 border-b border-white/10 bg-[#242424] px-3 text-white" aria-label="PDF zoom controls">
        <button className="grid size-9 place-items-center rounded-md text-white/80 hover:bg-white/10 hover:text-white disabled:opacity-35" type="button" disabled={zoom === 50} onClick={() => setZoom(current => nextPdfZoom(current, -1))} aria-label="Zoom out"><Minus size={17} /></button>
        <button className="min-h-9 min-w-16 rounded-md px-2 text-sm font-semibold tabular-nums text-white/90 hover:bg-white/10" type="button" onClick={() => setZoom(100)} aria-label={`Reset zoom, currently ${zoom}%`}>{zoom}%</button>
        <button className="grid size-9 place-items-center rounded-md text-white/80 hover:bg-white/10 hover:text-white disabled:opacity-35" type="button" disabled={zoom === 200} onClick={() => setZoom(current => nextPdfZoom(current, 1))} aria-label="Zoom in"><Plus size={17} /></button>
        {stale ? <span className="ml-3 text-xs text-white/60">Previous preview</span> : null}
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4 md:p-6" aria-label="Resume PDF pages">
        {error ? <div className="grid h-full place-items-center text-sm text-white/75" role="alert">{error}</div> : null}
        {!document && !error ? <div className="grid h-full place-items-center text-sm text-white/70" role="status">Rendering PDF…</div> : null}
        {document ? <div className="mx-auto flex w-max min-w-full flex-col items-center gap-5">{Array.from({ length: document.numPages }, (_, index) => <PdfPage key={index + 1} document={document} pageNumber={index + 1} zoom={zoom} />)}</div> : null}
      </div>
    </div>
  )
}

function PdfPage({ document, pageNumber, zoom }: { document: PDFDocumentProxy; pageNumber: number; zoom: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    let page: PDFPageProxy | undefined
    let renderTask: RenderTask | undefined
    let active = true
    void document.getPage(pageNumber).then(loadedPage => {
      page = loadedPage
      const canvas = canvasRef.current
      if (!canvas || !active) return
      const viewport = loadedPage.getViewport({ scale: 1.25 * zoom / 100 })
      const pixelRatio = window.devicePixelRatio || 1
      canvas.width = Math.floor(viewport.width * pixelRatio)
      canvas.height = Math.floor(viewport.height * pixelRatio)
      canvas.style.width = `${Math.floor(viewport.width)}px`
      canvas.style.height = `${Math.floor(viewport.height)}px`
      const context = canvas.getContext('2d')
      if (!context) return
      renderTask = loadedPage.render({ canvas, canvasContext: context, viewport, transform: pixelRatio === 1 ? undefined : [pixelRatio, 0, 0, pixelRatio, 0, 0] })
      return renderTask.promise
    }).catch(error => {
      if (error?.name !== 'RenderingCancelledException') throw error
    })
    return () => {
      active = false
      renderTask?.cancel()
      page?.cleanup()
    }
  }, [document, pageNumber, zoom])

  return <canvas ref={canvasRef} className="bg-white shadow-lg" aria-label={`PDF page ${pageNumber}`} />
}
