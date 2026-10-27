import { type FormEvent, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  cancelReviewJob,
  fetchReviewJob,
  startReview,
  type ModelConfiguration,
  type ReviewJob,
} from "@/lib/api";

export function ReviewPanel({ model }: { model: ModelConfiguration }) {
  const [repositoryPath, setRepositoryPath] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<ReviewJob | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const path = repositoryPath.trim();
    if (path === "") {
      return;
    }
    setPending(true);
    setError(null);
    setJob(null);
    try {
      const started = await startReview(path, confirmed);
      setJob(started);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The local review could not be started.");
    } finally {
      setPending(false);
    }
  }

  const blocked = model.large_model && !confirmed;
  const running = job?.status === "running";

  useEffect(() => {
    if (!job || job.status !== "running") {
      return;
    }
    let stopped = false;
    const timer = window.setInterval(() => {
      void fetchReviewJob(job.id)
        .then((next) => {
          if (!stopped) {
            setJob(next);
          }
        })
        .catch((caught: unknown) => {
          if (!stopped) {
            setError(caught instanceof Error ? caught.message : "The local review could not be read.");
          }
        });
    }, 400);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [job]);

  async function onCancel() {
    if (!job) {
      return;
    }
    setError(null);
    try {
      setJob(await cancelReviewJob(job.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The local review could not be cancelled.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Review</CardTitle>
        <CardDescription>
          Starting a review is the action that contacts Ollama. The diff is sent in bounded chunks.
          Findings are checked against a schema and are not treated as proven.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-3" data-testid="review-form" onSubmit={onSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="review-path">Repository path</Label>
            <Input
              id="review-path"
              value={repositoryPath}
              onChange={(event) => setRepositoryPath(event.target.value)}
              placeholder="/absolute/path/to/repository"
              autoComplete="off"
            />
          </div>
          {model.large_model ? (
            <label className="flex items-start gap-2 text-sm" data-testid="large-model-warning">
              <input
                type="checkbox"
                className="mt-1"
                checked={confirmed}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              <span>{model.memory_warning}</span>
            </label>
          ) : null}
          <div className="flex gap-2">
            <Button type="submit" disabled={pending || running || repositoryPath.trim() === "" || blocked}>
              Start review
            </Button>
            {running ? (
              <Button type="button" variant="outline" onClick={() => void onCancel()}>
                Cancel review
              </Button>
            ) : null}
          </div>
          {error ? (
            <Alert variant="destructive" data-testid="review-error">
              <AlertTitle>Review was not completed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {job ? <ReviewResult job={job} /> : null}
        </form>
      </CardContent>
    </Card>
  );
}

function ReviewResult({ job }: { job: ReviewJob }) {
  return (
    <div className="flex flex-col gap-3" data-testid="review-result">
      <p className="text-sm">{job.message}</p>
      {job.setup_instruction ? <p className="text-sm">{job.setup_instruction}</p> : null}
      {job.errors.length > 0 ? (
        <ul className="list-disc pl-5 text-sm" data-testid="review-errors">
          {job.errors.map((item, index) => (
            <li key={`${index}:${item}`}>{item}</li>
          ))}
        </ul>
      ) : null}
      {job.retry.length > 0 ? (
        <ul className="list-disc pl-5 text-sm" data-testid="review-retry">
          {job.retry.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ul>
      ) : null}
      {job.findings.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {job.findings.map((finding) => (
            <li key={`${finding.path}:${finding.line_start}:${finding.summary}`} className="rounded-md border p-3 text-sm">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="font-medium">
                  {finding.path}:{finding.line_start}
                </span>
                <Badge>{finding.uncertain ? "Uncertain" : "Reported"}</Badge>
              </div>
              <p>{finding.summary}</p>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="text-xs text-muted-foreground">
        Reported findings matched the schema and the changed lines. They are still model output.
        Uncertain findings are not treated as defects.
      </p>
    </div>
  );
}
