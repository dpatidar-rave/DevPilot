import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppShell } from '@/components/layout/AppShell'

const health = {
  status: 'ok',
  version: '0.1.0',
  database: 'ok',
  database_message: null,
  bind_host: '127.0.0.1',
  ai: {
    provider: 'ollama',
    endpoint: 'http://127.0.0.1:11434',
    model: 'qwen2.5-coder:7b',
    context_length: 8192,
    temperature: 0.1,
    max_output_tokens: 1800,
    timeout_seconds: 180,
    keep_alive: '10m',
    max_concurrent_requests: 1,
    availability: 'not_checked',
    external_providers: [],
    large_model_confirmed: false,
  },
}

const settings = {
  provider: 'ollama',
  model: 'qwen2.5-coder:7b',
  context_length: 8192,
  temperature: 0.1,
  max_output_tokens: 1800,
  timeout_seconds: 180,
  keep_alive: '10m',
  ollama_endpoint: 'http://127.0.0.1:11434',
  max_concurrent_requests: 1,
  large_model_confirmed: false,
  availability: 'not_checked',
  external_providers: [],
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/api/health')) {
        return jsonResponse(health)
      }
      if (url.endsWith('/api/settings')) {
        return jsonResponse(settings)
      }
      if (
        url.endsWith('/api/projects') ||
        url.endsWith('/api/reviews') ||
        url.endsWith('/api/quality-checks') ||
        url.endsWith('/api/release-reports')
      ) {
        return jsonResponse({ items: [] })
      }
      throw new Error(`Unexpected request ${url}`)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function renderShell(path = '/') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppShell />
    </MemoryRouter>,
  )
}

describe('application shell', () => {
  it('shows the local model and does not invent findings', async () => {
    renderShell()

    expect((await screen.findAllByText('qwen2.5-coder:7b')).length).toBeGreaterThan(0)
    expect(screen.getByText('Not checked')).toBeInTheDocument()
    expect(screen.getByText('Connected')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Primary' })).toBeInTheDocument()
    expect(screen.getByText(/does not invent findings/i)).toBeInTheDocument()
  })

  it('opens the reviews page from the sidebar', async () => {
    const user = userEvent.setup()
    renderShell()
    await screen.findAllByText('qwen2.5-coder:7b')

    await user.click(screen.getByRole('link', { name: 'Reviews' }))

    expect(await screen.findByText(/does not create sample findings/i)).toBeInTheDocument()
  })

  it('explains how to retry when the backend is down', async () => {
    vi.unstubAllGlobals()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('connect ECONNREFUSED')))
    const user = userEvent.setup()
    renderShell()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/will not switch to a hosted provider/i)
    expect(alert).toHaveTextContent(/scripts\/start.sh/)
    expect(screen.queryByText(/openai/i)).not.toBeInTheDocument()

    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse(health)),
    )
    await user.click(screen.getByRole('button', { name: 'Retry' }))
    expect((await screen.findAllByText('qwen2.5-coder:7b')).length).toBeGreaterThan(0)
  })
})
