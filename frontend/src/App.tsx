import { Shield } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { InspectPanel } from "@/components/InspectPanel";
import { ReviewPanel } from "@/components/ReviewPanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { loadDashboard, type DashboardData, type StoredReview } from "@/lib/api";

export function App() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setData(await loadDashboard());
    } catch (error) {
      setData(null);
      setLoadError(
        error instanceof Error ? error.message : "Cannot reach the DevPilot API on this machine.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-screen">
      <header className="border-b">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-6 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Shield className="size-5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-lg font-semibold tracking-tight">DevPilot</p>
              <p className="text-sm text-muted-foreground">Local code review and release quality</p>
            </div>
          </div>
          <Badge data-testid="privacy-banner">Local only · Ollama · SQLite</Badge>
        </div>
      </header>
      <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-6">
        <p className="text-sm text-muted-foreground" data-testid="privacy-copy">
          Source code, Git diffs, reviews, and the database stay on this machine. Ollama is contacted
          when you start a review. A missing model or a connection problem is shown then, with setup
          steps. DevPilot does not download models or switch to a hosted model.
        </p>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-sm font-medium">Local status</h1>
          <Button type="button" variant="outline" size="sm" onClick={() => void load()}>
            Retry local checks
          </Button>
        </div>
        {loading && data === null ? <p>Checking the local API…</p> : null}
        {loadError ? (
          <Alert variant="destructive" data-testid="api-error">
            <AlertTitle>Local API unavailable</AlertTitle>
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
        ) : null}
        {data ? <Dashboard data={data} /> : null}
      </main>
    </div>
  );
}

function Dashboard({ data }: { data: DashboardData }) {
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <StatusColumn data={data} />
      <div className="flex flex-col gap-6">
        <InspectPanel />
        <ReviewPanel model={data.system.model} />
        <ReviewsCard reviews={data.reviews} reportSummary={data.report?.summary ?? null} />
      </div>
    </div>
  );
}

function StatusColumn({ data }: { data: DashboardData }) {
  const model = data.system.model;
  const database = data.system.database;
  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Model</CardTitle>
          <CardDescription>
            {data.system.ai_provider} at {model.endpoint}. Availability is checked when you start a
            review.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2 text-sm" data-testid="model-config">
          <p>Model {model.name}</p>
          <p>Context {model.context_length} tokens</p>
          <p>Temperature {model.temperature}</p>
          <p>Maximum output {model.max_output_tokens} tokens</p>
          <p>Timeout {model.timeout_seconds} seconds</p>
          <p>Keep-alive {model.keep_alive}</p>
          <p data-testid="model-availability">Availability: {model.availability}</p>
          {model.memory_warning ? (
            <Alert data-testid="model-memory-warning">
              <AlertTitle>Optional large model</AlertTitle>
              <AlertDescription>{model.memory_warning}</AlertDescription>
            </Alert>
          ) : null}
          {database.ready ? (
            <p data-testid="database-ok">SQLite is ready on this machine.</p>
          ) : (
            <Alert variant="destructive" data-testid="database-alert">
              <AlertTitle>Local database is not ready</AlertTitle>
              <AlertDescription>
                <p>{database.error}</p>
                <ul className="mt-2 list-disc pl-5">
                  {database.retry.map((step) => (
                    <li key={step}>{step}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Quality checks</CardTitle>
          <CardDescription>
            Listing a check does not run it. This version has no check runner, so nothing is
            executed from this screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {data.checks.map((check) => (
            <div key={check.check_id} className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{check.check_id}</p>
                <p className="text-sm text-muted-foreground">{check.description}</p>
              </div>
              <Badge>{check.executed ? "Executed" : "Not executed"}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ReviewsCard({
  reviews,
  reportSummary,
}: {
  reviews: StoredReview[] | null;
  reportSummary: string | null;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Reviews and release report</CardTitle>
        <CardDescription>Rows come from the local database. Nothing here is invented.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {reportSummary ? <p className="text-sm">{reportSummary}</p> : null}
        {reviews === null ? (
          <p className="text-sm text-muted-foreground" data-testid="reviews-unavailable">
            Reviews are unavailable until the local database is migrated.
          </p>
        ) : reviews.length === 0 ? (
          <p className="text-sm" data-testid="reviews-empty">
            No reviews are stored on this machine.
          </p>
        ) : (
          <ul className="flex flex-col gap-3" data-testid="reviews-list">
            {reviews.map((review) => (
              <li key={review.id} className="rounded-md border p-3 text-sm">
                <p className="font-medium">{review.repository_path}</p>
                <p className="text-muted-foreground">
                  {review.status} · {review.created_at}
                </p>
                <p>{review.summary}</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
