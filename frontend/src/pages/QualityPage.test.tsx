import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { QualityPage } from '@/pages/QualityPage'
import {
  listProjects,
  listQualityChecks,
  listReviews,
  readQualityCatalog,
  runQualityCheck,
  saveQualityCommand,
} from '@/services/api'

vi.mock('@/services/api', () => ({
  listProjects: vi.fn(),
  listQualityChecks: vi.fn(),
  listReviews: vi.fn(),
  readQualityCatalog: vi.fn(),
  runQualityCheck: vi.fn(),
  saveQualityCommand: vi.fn(),
}))

const project = {
  id: 'p1',
  name: 'Fixture',
  path: '/tmp/fixture',
  created_at: '2026-10-27T00:00:00+00:00',
  updated_at: '2026-10-27T00:00:00+00:00',
  branch: 'main',
  detached: false,
  dirty: false,
  magento: false,
  inspection_error: null,
}

const catalog = {
  project_id: 'p1',
  working_directory: '/tmp/fixture',
  warning: 'Approved project scripts can still have side effects.',
  tools: [
    {
      tool: 'phpunit',
      label: 'PHPUnit',
      available: true,
      files: ['phpunit.xml'],
      suggested_argv: ['php', 'vendor/bin/phpunit'],
      saved_argv: ['php', 'vendor/bin/phpunit'],
      reason: null,
    },
  ],
}

beforeEach(() => {
  vi.mocked(listProjects).mockResolvedValue([project])
  vi.mocked(readQualityCatalog).mockResolvedValue(catalog)
  vi.mocked(listQualityChecks).mockResolvedValue([])
  vi.mocked(listReviews).mockResolvedValue([])
  vi.mocked(saveQualityCommand).mockResolvedValue()
  vi.mocked(runQualityCheck).mockResolvedValue({
    id: 'run-1',
    project_id: 'p1',
    review_id: null,
    status: 'failed',
    result: 'fail',
    tool: 'phpunit',
    command: 'php vendor/bin/phpunit',
    argv: ['php', 'vendor/bin/phpunit'],
    working_directory: '/tmp/fixture',
    started_at: '2026-10-27T00:00:00+00:00',
    finished_at: '2026-10-27T00:00:01+00:00',
    duration_ms: 1000,
    exit_code: 2,
    stdout: '',
    stderr: 'bad',
    output_truncated: false,
    note: 'Exited 2.',
    created_at: '2026-10-27T00:00:00+00:00',
    origin: 'command_result',
  })
})

describe('quality checks', () => {
  it('requires a saved command and a confirmation before it runs', async () => {
    const user = userEvent.setup()
    render(<QualityPage />)

    expect(screen.getByText(/side effects/i)).toBeInTheDocument()
    expect(runQualityCheck).not.toHaveBeenCalled()

    await user.selectOptions(await screen.findByLabelText('Repository'), 'p1')
    const section = (await screen.findByRole('heading', { name: 'PHPUnit' })).closest('section')
    expect(section).not.toBeNull()
    const view = within(section as HTMLElement)
    const run = view.getByRole('button', { name: 'Run saved command' })
    expect(run).toBeDisabled()

    await user.click(view.getByLabelText('I confirm this run'))
    expect(run).toBeEnabled()
    await user.click(run)

    expect(runQualityCheck).toHaveBeenCalledWith('p1', 'phpunit', true, null)
    expect(saveQualityCommand).not.toHaveBeenCalled()
  })
})
