import { describe, expect, it } from 'vitest'

import config from '../vite.config'

describe('dev server binding', () => {
  it('serves the UI on loopback only', () => {
    const resolved = typeof config === 'function' ? undefined : config
    expect(resolved?.server?.host).toBe('127.0.0.1')
    expect(resolved?.preview?.host).toBe('127.0.0.1')
  })
})
