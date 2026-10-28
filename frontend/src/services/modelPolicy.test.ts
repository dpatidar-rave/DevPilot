import { describe, expect, it } from 'vitest'

import { endpointError, modelError, settingsPayload } from '@/services/modelPolicy'

describe('model policy', () => {
  it('accepts the local default and rejects hosted names', () => {
    expect(modelError('qwen2.5-coder:7b', false)).toBeNull()
    expect(modelError('gpt-4o', false)).toMatch(/Hosted model names/)
    expect(modelError('claude-3-5-sonnet', false)).toMatch(/Hosted model names/)
    expect(modelError('gemini-1.5-pro', false)).toMatch(/Hosted model names/)
    expect(modelError('gemma2:9b', false)).toBeNull()
  })

  it('requires confirmation for a 20B experiment', () => {
    expect(modelError('qwen2.5-coder:20b', false)).toMatch(/16 GB/)
    expect(modelError('qwen2.5-coder:20b', true)).toBeNull()
  })

  it('accepts only a loopback Ollama origin', () => {
    expect(endpointError('http://127.0.0.1:11434')).toBeNull()
    expect(endpointError('http://localhost:11434')).toBeNull()
    expect(endpointError('http://[::1]:11434')).toBeNull()
    expect(endpointError('http://10.1.2.3:11434')).toMatch(/loopback/)
    expect(endpointError('http://127.0.0.1:11434/v1')).toMatch(/path/)
  })

  it('builds a payload only when the draft is local', () => {
    const rejected = settingsPayload({
      model: 'gpt-4o',
      contextLength: '8192',
      temperature: '0.1',
      maxOutputTokens: '1800',
      timeoutSeconds: '180',
      ollamaEndpoint: 'http://127.0.0.1:11434',
      largeModelConfirmed: false,
    })
    expect(rejected.ok).toBe(false)

    const accepted = settingsPayload({
      model: 'qwen2.5-coder:7b',
      contextLength: '8192',
      temperature: '0.1',
      maxOutputTokens: '1800',
      timeoutSeconds: '180',
      ollamaEndpoint: 'http://127.0.0.1:11434',
      largeModelConfirmed: false,
    })
    expect(accepted).toMatchObject({
      ok: true,
      body: { model: 'qwen2.5-coder:7b', context_length: 8192, large_model_confirmed: false },
    })
  })
})
