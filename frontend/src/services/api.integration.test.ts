/**
 * @vitest-environment node
 */
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync, mkdtempSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { afterAll, describe, expect, it } from 'vitest'

import { checkHealth, listReviews } from '@/services/api'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..')
const backendDir = path.join(repoRoot, 'backend')
const python = path.join(backendDir, '.venv/bin/python')

describe('frontend reaches the local backend', () => {
  let child: ChildProcess | undefined
  let port = 0

  afterAll(async () => {
    await stop(child)
  })

  it('reads health and an empty review list from the running API', async () => {
    expect(existsSync(python), 'Run scripts/setup.sh before this test.').toBe(true)
    port = await freePort()
    const work = mkdtempSync(path.join(tmpdir(), 'devpilot-ui-'))
    child = spawn(python, ['-m', 'app'], {
      cwd: backendDir,
      env: {
        PATH: process.env.PATH ?? '',
        HOME: process.env.HOME ?? '',
        TMPDIR: process.env.TMPDIR ?? '/tmp',
        LANG: process.env.LANG ?? 'C.UTF-8',
        PYTHONUNBUFFERED: '1',
        DEVPILOT_DISABLE_ENV_FILE: '1',
        DEVPILOT_HOST: '127.0.0.1',
        DEVPILOT_PORT: String(port),
        DEVPILOT_DATABASE_URL: `sqlite:///${path.join(work, 'devpilot.db')}`,
        DEVPILOT_LOG_DIR: path.join(work, 'logs'),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const logs: Buffer[] = []
    child.stdout?.on('data', (chunk: Buffer) => logs.push(chunk))
    child.stderr?.on('data', (chunk: Buffer) => logs.push(chunk))

    try {
      await waitForHealth(port)
    } catch (error) {
      throw new Error(`${String(error)}\n${Buffer.concat(logs).toString('utf8')}`)
    }

    const base = `http://127.0.0.1:${port}`
    const health = await checkHealth(base)
    const reviews = await listReviews(base)

    expect(health.status).toBe('ok')
    expect(health.bind_host).toBe('127.0.0.1')
    expect(health.database).toBe('ok')
    expect(health.ai.provider).toBe('ollama')
    expect(health.ai.model).toBe('qwen2.5-coder:7b')
    expect(health.ai.context_length).toBe(8192)
    expect(health.ai.availability).toBe('not_checked')
    expect(health.ai.external_providers).toEqual([])
    expect(reviews).toEqual([])
  })
})

function freePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (address && typeof address === 'object') {
        const selected = address.port
        server.close(() => resolve(selected))
        return
      }
      reject(new Error('Could not reserve a local port.'))
    })
  })
}

async function waitForHealth(port: number): Promise<void> {
  const deadline = Date.now() + 20000
  let last = 'backend did not become healthy'
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/api/health`)
      if (response.ok) {
        return
      }
      last = `HTTP ${response.status}`
    } catch (error) {
      last = error instanceof Error ? error.message : 'connection failed'
    }
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  throw new Error(last)
}

async function stop(child: ChildProcess | undefined): Promise<void> {
  if (!child || child.exitCode !== null) {
    return
  }
  child.kill('SIGTERM')
  await new Promise((resolve) => {
    const timer = setTimeout(() => {
      child.kill('SIGKILL')
      resolve(undefined)
    }, 5000)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve(undefined)
    })
  })
}
