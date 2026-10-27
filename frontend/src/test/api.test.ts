import { describe, expect, it, vi } from "vitest";

import { apiFetch, assertLocalProvider, assertLoopbackApiBase, LOCAL_API_ORIGIN } from "@/lib/api";
import type { SystemStatus } from "@/lib/api";

describe("loopback guard", () => {
  it("accepts the local API origin", () => {
    expect(LOCAL_API_ORIGIN).toBe("http://127.0.0.1:8000");
    expect(() => assertLoopbackApiBase(LOCAL_API_ORIGIN)).not.toThrow();
  });

  it("rejects hosted and non-http bases", () => {
    expect(() => assertLoopbackApiBase("https://example.com")).toThrow(/localhost/i);
    expect(() => assertLoopbackApiBase("http://10.0.0.8:8000")).toThrow(/localhost/i);
    expect(() => assertLoopbackApiBase("https://127.0.0.1:8000")).toThrow(/localhost/i);
  });
});

describe("apiFetch", () => {
  it("refuses a path that is not the local API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    await expect(apiFetch("https://example.com/v1")).rejects.toThrow(/non-local/i);
    expect(fetchMock).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});

describe("provider guard", () => {
  it("rejects a fallback provider", () => {
    const status = baseStatus();
    status.fallback_used = true;
    expect(() => assertLocalProvider(status)).toThrow(/non-local/i);
  });
});

function baseStatus(): SystemStatus {
  return {
    api: "ok",
    bind_host: "127.0.0.1",
    ai_provider: "ollama-local",
    fallback_used: false,
    database: { ready: true, error: null, retry: [] },
    model: {
      name: "qwen2.5-coder:7b",
      context_length: 8192,
      temperature: 0.1,
      max_output_tokens: 1800,
      timeout_seconds: 120,
      keep_alive: "10m",
      endpoint: "http://127.0.0.1:11434",
      availability: "not_checked",
      large_model: false,
      memory_warning: null,
    },
  };
}
