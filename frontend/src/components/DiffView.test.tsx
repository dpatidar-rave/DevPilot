import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DiffView, sanitizeHighlight } from '@/components/DiffView'

function codeText(text: string) {
  return (_content: string, element: Element | null) =>
    element?.tagName === 'CODE' && element.textContent === text
}

describe('diff view', () => {
  it('marks added and deleted lines', () => {
    render(
      <DiffView
        language="php"
        binary={false}
        truncated={false}
        skipped={null}
        lines={[
          { kind: 'delete', text: 'return false;', old_line: 4, new_line: null },
          { kind: 'add', text: 'return true;', old_line: null, new_line: 4 },
        ]}
      />,
    )

    expect(screen.getByLabelText('Deleted')).toBeInTheDocument()
    expect(screen.getByLabelText('Added')).toBeInTheDocument()
    expect(screen.getByText(codeText('return false;'))).toBeInTheDocument()
    expect(screen.getByText(codeText('return true;'))).toBeInTheDocument()
  })

  it('does not render credential file contents', () => {
    render(
      <DiffView
        language={null}
        binary={false}
        truncated={false}
        skipped="sensitive"
        lines={[{ kind: 'add', text: 'secret', old_line: null, new_line: 1 }]}
      />,
    )

    expect(screen.getByText(/does not read it/i)).toBeInTheDocument()
    expect(screen.queryByText('secret')).not.toBeInTheDocument()
  })

  it('escapes markup that is not a highlight span', () => {
    const html = sanitizeHighlight(
      '<span class="hljs-keyword">echo</span><img src=x onerror="alert(1)">',
    )
    expect(html).toContain('<span class="hljs-keyword">')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
    const attribute = sanitizeHighlight('<span class="hljs-keyword" onclick="alert(1)">')
    expect(attribute).not.toContain('<span')
    expect(attribute).toContain('&lt;span')

    const { container } = render(
      <DiffView
        language="php"
        binary={false}
        truncated={false}
        skipped={null}
        lines={[{ kind: 'add', text: '<script>alert(1)</script>', old_line: null, new_line: 1 }]}
      />,
    )
    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText(codeText('<script>alert(1)</script>'))).toBeInTheDocument()
  })
})
