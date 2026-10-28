import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, checkHealth } from '@/services/api'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client', () => {
  it('refuses a remote backend before sending a request', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    await expect(checkHealth('http://api.example.com:8000')).rejects.toBeInstanceOf(ApiError)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejects a health payload that names an external provider', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          status: 'ok',
          version: '0.1.0',
          database: 'ok',
          database_message: null,
          bind_host: '127.0.0.1',
          ai: {
            provider: 'openai',
            endpoint: 'https://api.openai.com',
            model: 'gpt-4o',
            availability: 'not_checked',
            external_providers: ['openai'],
          },
        }),
      }),
    )

    await expect(checkHealth('http://127.0.0.1:8000')).rejects.toThrow(/external AI provider/)
  })
})
