import hljs from 'highlight.js/lib/core'
import bash from 'highlight.js/lib/languages/bash'
import css from 'highlight.js/lib/languages/css'
import ini from 'highlight.js/lib/languages/ini'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import markdown from 'highlight.js/lib/languages/markdown'
import php from 'highlight.js/lib/languages/php'
import scss from 'highlight.js/lib/languages/scss'
import sql from 'highlight.js/lib/languages/sql'
import xml from 'highlight.js/lib/languages/xml'
import yaml from 'highlight.js/lib/languages/yaml'

import type { DiffLine } from '@/services/api'

let languagesReady = false

function ensureLanguages(): void {
  if (languagesReady) {
    return
  }
  hljs.registerLanguage('php', php)
  hljs.registerLanguage('xml', xml)
  hljs.registerLanguage('json', json)
  hljs.registerLanguage('javascript', javascript)
  hljs.registerLanguage('css', css)
  hljs.registerLanguage('scss', scss)
  hljs.registerLanguage('bash', bash)
  hljs.registerLanguage('sql', sql)
  hljs.registerLanguage('ini', ini)
  hljs.registerLanguage('yaml', yaml)
  hljs.registerLanguage('markdown', markdown)
  languagesReady = true
}

export function DiffView({
  lines,
  language,
  binary,
  truncated,
  skipped,
}: {
  lines: DiffLine[]
  language: string | null
  binary: boolean
  truncated: boolean
  skipped: 'generated' | 'sensitive' | null
}) {
  if (skipped === 'sensitive') {
    return (
      <p className="text-sm text-muted-foreground">
        This file was not opened. It may contain credentials, and DevPilot does not read it.
      </p>
    )
  }
  if (skipped === 'generated') {
    return (
      <p className="text-sm text-muted-foreground">
        This path is in a generated directory, so its diff was not loaded.
      </p>
    )
  }
  if (binary) {
    return <p className="text-sm text-muted-foreground">Binary file. Its contents are not shown.</p>
  }
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-card">
      {truncated && (
        <p className="border-b border-border px-3 py-2 text-xs text-muted-foreground">
          This diff was truncated so a large change does not fill the page.
        </p>
      )}
      <ol className="font-mono text-xs leading-5">
        {lines.map((line, index) => (
          <DiffRow key={`${line.kind}-${index}-${line.old_line}-${line.new_line}`} line={line} language={language} />
        ))}
      </ol>
    </div>
  )
}

function DiffRow({ line, language }: { line: DiffLine; language: string | null }) {
  if (line.kind === 'meta') {
    return <li className="bg-muted px-3 text-muted-foreground">{line.text}</li>
  }
  const marker = line.kind === 'add' ? '+' : line.kind === 'delete' ? '−' : ' '
  const label = line.kind === 'add' ? 'Added' : line.kind === 'delete' ? 'Deleted' : 'Context'
  return (
    <li className={line.kind === 'add' ? 'diff-add' : line.kind === 'delete' ? 'diff-delete' : undefined}>
      <span className="inline-block w-12 select-none px-2 text-right text-muted-foreground">
        {line.old_line ?? ''}
      </span>
      <span className="inline-block w-12 select-none px-2 text-right text-muted-foreground">
        {line.new_line ?? ''}
      </span>
      <span className="inline-block w-4 select-none font-semibold" aria-label={label}>
        {marker}
      </span>
      <code dangerouslySetInnerHTML={{ __html: highlight(line.text, language) }} />
    </li>
  )
}

function highlight(text: string, language: string | null): string {
  ensureLanguages()
  if (!language || !hljs.getLanguage(language)) {
    return escapeHtml(text)
  }
  try {
    return hljs.highlight(text, { language, ignoreIllegals: true }).value
  } catch {
    return escapeHtml(text)
  }
}

function escapeHtml(text: string): string {
  return text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
}
