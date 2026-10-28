import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ReleaseReportView } from '@/components/ReleaseReportView'
import type { ReleaseAssessment } from '@/services/api'

const report: ReleaseAssessment = {
  readiness: 'blocked',
  statement:
    'This report does not approve the release. AI findings are suggestions, and a passing model review cannot make a release ready. A technical lead must decide.',
  blockers: ['Unresolved critical finding: Missing authorization'],
  warnings: [],
  passed: ['Code review completion'],
  waivers: [
    {
      text: 'critical: Missing authorization',
      reason: 'Accepted for this release.',
      reviewer: 'lead',
    },
  ],
  missing: ['Automated tests has no passing evidence.'],
  checklist: [
    {
      key: 'automated_tests',
      label: 'Automated tests',
      status: 'pending',
      evidence: 'No PHPUnit result is stored for this review.',
      reason: '',
      reviewer: '',
    },
    {
      key: 'critical_high',
      label: 'Critical and high-severity findings',
      status: 'waived',
      evidence: 'Every critical or high finding was waived or dismissed individually.',
      reason: '',
      reviewer: '',
    },
  ],
  findings: [
    {
      id: 'f1',
      severity: 'critical',
      title: 'Missing authorization',
      file_path: 'Controller.php',
      decision: 'waived',
      reason: 'Accepted for this release.',
      reviewer: 'lead',
    },
  ],
  quality: [],
  model: {
    name: 'qwen2.5-coder:7b',
    context_length: 8192,
    temperature: 0.1,
    max_output_tokens: 1800,
    timeout_seconds: 180,
  },
  project_id: 'p',
  project_name: 'Fixture',
  review_id: 'review-1',
  review_status: 'completed',
  base_ref: 'main',
  head_sha: 'abc123',
  repository_head_sha: 'def456',
  dirty: false,
  generated_at: '2026-10-27T18:00:00+00:00',
  limitations: [],
}

describe('ReleaseReportView', () => {
  it('shows blockers, a waiver with its reason, and does not list that waiver as passed', () => {
    render(<ReleaseReportView report={report} />)

    expect(screen.getByRole('heading', { name: 'Blocked' })).toBeInTheDocument()
    expect(screen.getByText(/does not approve the release/)).toBeInTheDocument()
    expect(screen.getByText('Unresolved critical finding: Missing authorization')).toBeInTheDocument()
    expect(screen.getAllByText(/Accepted for this release/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Reviewer: lead/).length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Passed checks' })).toBeInTheDocument()
    expect(screen.getByText('Code review completion')).toBeInTheDocument()
    const passed = screen.getByRole('heading', { name: 'Passed checks' }).parentElement
    expect(passed?.textContent).not.toContain('Missing authorization')
    expect(screen.getByText('Automated tests has no passing evidence.')).toBeInTheDocument()
    expect(screen.getByText('qwen2.5-coder:7b')).toBeInTheDocument()
    expect(screen.getByText('abc123')).toBeInTheDocument()
    expect(screen.getByText('Waived — critical: Missing authorization')).toBeInTheDocument()
  })
})
