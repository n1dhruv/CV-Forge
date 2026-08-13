export function validDiagnosticLine(line: number | null | undefined, source: string) {
  if (!line || line < 1 || line > source.split('\n').length) return undefined
  return line
}

export function shouldShowCompileDiagnostics(versionStatus: string | undefined, jobStatus: string | undefined) {
  return versionStatus !== 'compiled' && jobStatus === 'failed'
}

export function nextPdfZoom(current: number, direction: -1 | 1) {
  return Math.min(200, Math.max(50, current + direction * 10))
}

export function resumePdfFilename(name: string) {
  const safe = name.trim().replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '')
  return `${safe || 'resume'}.pdf`
}

export async function downloadPdf(url: string, filename: string) {
  const response = await fetch(url)
  if (!response.ok) throw new Error('The PDF could not be downloaded.')
  const objectUrl = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = resumePdfFilename(filename)
  anchor.click()
  URL.revokeObjectURL(objectUrl)
}
