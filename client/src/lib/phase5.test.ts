import assert from 'node:assert/strict'
import test from 'node:test'
import { validDiagnosticLine } from './resume-editor.ts'
import { nextPdfZoom, shouldShowCompileDiagnostics } from './resume-editor.ts'
import { downloadPdf, resumePdfFilename } from './resume-editor.ts'

test('diagnostic markers are created only for valid source lines', () => {
  assert.equal(validDiagnosticLine(2, 'first\nsecond'), 2)
  assert.equal(validDiagnosticLine(0, 'first'), undefined)
  assert.equal(validDiagnosticLine(3, 'first\nsecond'), undefined)
  assert.equal(validDiagnosticLine(undefined, 'first'), undefined)
})

test('old job diagnostics are hidden after the version compiles', () => {
  assert.equal(shouldShowCompileDiagnostics('compiled', 'failed'), false)
  assert.equal(shouldShowCompileDiagnostics('compile_failed', 'failed'), true)
})

test('PDF zoom changes in ten-point steps within its limits', () => {
  assert.equal(nextPdfZoom(100, 1), 110)
  assert.equal(nextPdfZoom(195, 1), 200)
  assert.equal(nextPdfZoom(55, -1), 50)
})

test('resume download filenames are safe and useful', () => {
  assert.equal(resumePdfFilename(' Backend / Final '), 'Backend-Final.pdf')
  assert.equal(resumePdfFilename('***'), 'resume.pdf')
})

test('PDF downloads use a temporary object URL and clean it up', async () => {
  const originalFetch = globalThis.fetch
  const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document')
  const originalCreate = Object.getOwnPropertyDescriptor(URL, 'createObjectURL')
  const originalRevoke = Object.getOwnPropertyDescriptor(URL, 'revokeObjectURL')
  let clicked = false
  let downloadedAs = ''
  let revoked = ''

  globalThis.fetch = async () => new Response('pdf')
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { createElement: () => ({ href: '', set download(value: string) { downloadedAs = value }, click: () => { clicked = true } }) } })
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: () => 'blob:resume' })
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: (url: string) => { revoked = url } })

  try {
    await downloadPdf('https://storage.test/resume', 'Backend Final')
  } finally {
    globalThis.fetch = originalFetch
    if (originalDocument) Object.defineProperty(globalThis, 'document', originalDocument)
    else delete (globalThis as { document?: unknown }).document
    if (originalCreate) Object.defineProperty(URL, 'createObjectURL', originalCreate)
    if (originalRevoke) Object.defineProperty(URL, 'revokeObjectURL', originalRevoke)
  }

  assert.equal(clicked, true)
  assert.equal(downloadedAs, 'Backend-Final.pdf')
  assert.equal(revoked, 'blob:resume')
})
