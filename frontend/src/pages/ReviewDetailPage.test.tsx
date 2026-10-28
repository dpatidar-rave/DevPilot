import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ReviewDetailPage } from '@/pages/ReviewDetailPage'

const review = {
  id: 'review-1',
  project_id: 'project-1',
  status: 'completed',
  base_ref: 'main',
  head_ref: 'abc123',
  model: 'qwen2.5-coder:7b',
  context_length: 8192,
  created_at: '2026-10-27T00:00:00+00:00',
  finding_count: 1,
  error_code: null,
  error_message: null,
  summary: 'Local review with qwen2.5-coder:7b.',
  limitations: ['The diff for vendor/autoload.php was not sent.'],
  skipped_files: [{ path: 'vendor/autoload.php', reason: 'Generated directory.' }],
  reviewed_files: ['app/code/Example.php'],
  files_reviewed: 1,
  files_skipped: 1,
  chunks_total: 1,
  chunks_completed: 1,
  temperature: 0.1,
  max_output_tokens: 1800,
  timeout_seconds: 180,
  keep_alive: '10m',
  findings: [
    {
      id: 'finding-1',
      stable_key: 'abc',
      file_path: 'app/code/Example.php',
      scope: 'unstaged',
      start_line: 12,
      end_line: 12,
      severity: 'high',
      category: 'performance',
      title: 'Loads in a loop',
      explanation: 'A model is loaded inside the loop.',
      evidence: 'return $this->load();',
      remediation: 'Load the collection once.',
      confidence: 0.8,
      uncertain: false,
      needs_human_verification: true,
      evidence_checked: true,
      origin: 'ai_suggestion',
    },
  ],
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.includes('/diff')) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            path: 'app/code/Example.php',
            scope: 'unstaged',
            binary: false,
            truncated: false,
            skipped: null,
            language: 'php',
            lines: [{ kind: 'add', text: 'return $this->load();', old_line: null, new_line: 12 }],
          }),
        }
      }
      return { ok: true, status: 200, json: async () => review }
    }),
  )
})

describe('review detail', () => {
  it('labels findings as AI suggestions and opens the linked diff', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/reviews/review-1']}>
        <Routes>
          <Route path="/reviews/:reviewId" element={<ReviewDetailPage />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByText(/not test failures/i)).toBeInTheDocument()
    expect(screen.getByText(/not guaranteed to be correct/i)).toBeInTheDocument()
    expect(screen.getByText('qwen2.5-coder:7b')).toBeInTheDocument()
    expect(screen.getByText(/1 file\(s\) reviewed/i)).toBeInTheDocument()
    expect(screen.getByText(/Generated directory/i)).toBeInTheDocument()
    expect(screen.getByText('AI suggestion')).toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Severity'), 'critical')
    expect(screen.getByText('No AI suggestions in this filter.')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Severity'), 'high')

    await user.click(screen.getByRole('button', { name: /loads in a loop/i }))

    expect(await screen.findByLabelText('Added')).toBeInTheDocument()
    expect(screen.getByText(/not a test failure/i)).toBeInTheDocument()
  })
})
