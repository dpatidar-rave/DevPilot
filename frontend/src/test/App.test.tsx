import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/App";

function statusBody() {
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

function checksBody() {
  return {
    checks: [
      {
        check_id: "phpstan",
        description: "PHPStan at the Magento project's configured level.",
        execution: "disabled",
        requires_explicit_approval: true,
        executed: false,
      },
    ],
  };
}

function emptyReviews() {
  return { reviews: [] };
}

function emptyReport() {
  return {
    records: [],
    summary: "No release report data is stored locally.",
    ai_provider: "ollama-local",
    fallback_used: false,
  };
}

function mockFetch(options?: { fail?: boolean; reviews?: unknown; reviewJob?: unknown }) {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    if (options?.fail) {
      throw new Error("network down");
    }
    if (url.endsWith("/api/system/status")) {
      return jsonResponse(statusBody());
    }
    if (url.endsWith("/api/quality-checks")) {
      return jsonResponse(checksBody());
    }
    if (url.endsWith("/api/reviews")) {
      return jsonResponse(options?.reviews ?? emptyReviews());
    }
    if (url.endsWith("/api/release-report")) {
      return jsonResponse(emptyReport());
    }
    if (url.endsWith("/api/reviews/start")) {
      return jsonResponse(
        options?.reviewJob ?? {
          id: "job-1",
          status: "failed",
          repository_path: "/work/store",
          message: "Ollama is not running on this machine.",
          findings: [],
          errors: [],
          setup_instruction: null,
          retry: ["Start Ollama on this machine with `ollama serve`."],
        },
      );
    }
    if (url.endsWith("/api/repository/inspect")) {
      return jsonResponse({
        path: "/work/store",
        read_only: true,
        inside_work_tree: true,
        branch: "main",
        status_porcelain: "## main\n?? <script>alert(1)</script>",
        truncated: false,
      });
    }
    throw new Error(`unexpected ${url}`);
  });
  return calls;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("App", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the configured model without contacting Ollama", async () => {
    const calls = mockFetch();
    render(<App />);
    expect(await screen.findByTestId("model-config")).toHaveTextContent("qwen2.5-coder:7b");
    expect(screen.getByTestId("model-config")).toHaveTextContent("Context 8192 tokens");
    expect(screen.getByTestId("model-availability")).toHaveTextContent("not_checked");
    expect(screen.getByTestId("reviews-empty")).toHaveTextContent("No reviews are stored");
    expect(calls.some((call) => call.url.includes("/api/reviews/start"))).toBe(false);
  });

  it("shows a connection error only after a review starts", async () => {
    const calls = mockFetch();
    render(<App />);
    await screen.findByTestId("model-availability");
    fireEvent.change(screen.getByLabelText("Repository path", { selector: "#review-path" }), {
      target: { value: "/work/store" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Start review" }));
    expect(await screen.findByTestId("review-result")).toHaveTextContent("Ollama is not running");
    expect(screen.getByTestId("review-retry")).toHaveTextContent("ollama serve");
    const reviewCall = calls.find((call) => call.url.includes("/api/reviews/start"));
    expect(reviewCall?.init?.body).toBe(
      JSON.stringify({ path: "/work/store", approved: true, confirm_large_model: false }),
    );
  });

  it("does not inspect a repository until the user submits", async () => {
    const calls = mockFetch();
    render(<App />);
    await screen.findByTestId("reviews-empty");
    expect(calls.some((call) => call.url.includes("/api/repository/inspect"))).toBe(false);

    fireEvent.change(screen.getByLabelText("Repository path", { selector: "#repository-path" }), {
      target: { value: "/work/store" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Inspect repository (read-only)" }));

    const status = await screen.findByTestId("git-status");
    expect(status).toHaveTextContent("<script>alert(1)</script>");
    expect(status.querySelector("script")).toBeNull();
    const inspectCall = calls.find((call) => call.url.includes("/api/repository/inspect"));
    expect(inspectCall?.init?.method).toBe("POST");
    expect(inspectCall?.init?.body).toBe(JSON.stringify({ path: "/work/store", approved: true }));
  });

  it("explains how to retry when the API cannot be reached", async () => {
    mockFetch({ fail: true });
    render(<App />);
    expect(await screen.findByTestId("api-error")).toHaveTextContent("python -m app");
    expect(screen.getByTestId("api-error")).toHaveTextContent("does not use a hosted API");
  });

  it("renders a stored review instead of an empty state", async () => {
    mockFetch({
      reviews: {
        reviews: [
          {
            id: 7,
            created_at: "2026-10-27T00:00:00Z",
            repository_path: "/work/store",
            status: "recorded",
            summary: "stored-from-test-only",
          },
        ],
      },
    });
    render(<App />);
    expect(await screen.findByTestId("reviews-list")).toHaveTextContent("stored-from-test-only");
    expect(screen.queryByTestId("reviews-empty")).not.toBeInTheDocument();
  });
});
