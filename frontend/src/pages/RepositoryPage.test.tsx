import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { RepositoryPage } from '@/pages/RepositoryPage'

const detail = {
  id: 'project-1',
  name: 'shop',
  path: '/tmp/shop',
  branch: 'feature',
  detached: false,
  head_sha: 'abc123def456',
  head_subject: 'feature',
  committed_at: '2026-10-27T00:00:00+00:00',
  branches: ['feature', 'main'],
  dirty: true,
  uncommitted_warning:
    'This repository has uncommitted changes. DevPilot will not commit, discard, or switch branches.',
  magento: {
    detected: true,
    edition: 'Magento Open Source',
    magento_version: '2.4.7-p3',
    php_version: '8.2.27',
  },
}

const changes = {
  base: 'main',
  branches: ['feature', 'main'],
  staged: [{ path: 'staged.php', status: 'A', skipped: null, selected: false }],
  unstaged: [{ path: 'base.php', status: 'M', skipped: null, selected: false }],
  committed: [{ path: 'feature.php', status: 'A', skipped: null, selected: true }],
  untracked: [{ path: 'notes.php', status: '?', skipped: null, selected: false }],
  dirty: true,
  truncated: false,
  uncommitted_warning: detail.uncommitted_warning,
  selected_paths: ['feature.php'],
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/changes')) {
        return { ok: true, status: 200, json: async () => changes }
      }
      if (url.includes('/diff')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            path: 'base.php',
            scope: 'unstaged',
            binary: false,
            truncated: false,
            skipped: null,
            language: 'php',
            lines: [
              { kind: 'delete', text: 'old', old_line: 1, new_line: null },
              { kind: 'add', text: 'new', old_line: null, new_line: 1 },
            ],
          }),
        }
      }
      return { ok: true, status: 200, json: async () => detail }
    }),
  )
})

describe('repository page', () => {
  it('shows status, separate change groups, and a file diff', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/repositories/project-1']}>
        <Routes>
          <Route path="/repositories/:projectId" element={<RepositoryPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('alert')).toHaveTextContent(/will not commit/i)
    expect(screen.getByText('Magento 2.4.7-p3')).toBeInTheDocument()
    expect(screen.getByText('PHP 8.2.27')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Staged changes' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Unstaged changes' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Committed differences' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Untracked files' })).toBeInTheDocument()
    expect(screen.getByText(/does not start a review/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /base.php/i }))

    expect(await screen.findByLabelText('Added')).toBeInTheDocument()
    expect(screen.getByLabelText('Deleted')).toBeInTheDocument()
  })
})
