import { type FormEvent, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { inspectRepository, type Inspection } from "@/lib/api";

export function InspectPanel() {
  const [repositoryPath, setRepositoryPath] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Inspection | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const path = repositoryPath.trim();
    if (path === "") {
      return;
    }
    setPending(true);
    setError(null);
    try {
      setResult(await inspectRepository(path));
    } catch (caught) {
      setResult(null);
      setError(caught instanceof Error ? caught.message : "Git inspection failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Repository</CardTitle>
        <CardDescription>
          Read-only Git status runs only after you submit this form. Commit, push, merge, reset,
          clean, and branch switching are blocked.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="flex flex-col gap-3" data-testid="inspect-form" onSubmit={onSubmit}>
          <div className="flex flex-col gap-2">
            <Label htmlFor="repository-path">Repository path</Label>
            <Input
              id="repository-path"
              name="repository-path"
              value={repositoryPath}
              onChange={(event) => setRepositoryPath(event.target.value)}
              placeholder="/absolute/path/to/repository"
              autoComplete="off"
            />
          </div>
          <Button type="submit" disabled={pending || repositoryPath.trim() === ""}>
            Inspect repository (read-only)
          </Button>
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Inspection was not completed</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          {result ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm">
                Branch <span className="font-medium">{result.branch}</span>
                {result.truncated ? " · output truncated" : ""}
              </p>
              <pre
                data-testid="git-status"
                className="overflow-auto rounded-md border bg-muted p-3 text-xs"
              >
                {result.status_porcelain}
              </pre>
              <p className="text-xs text-muted-foreground">
                This output is untrusted repository text. DevPilot shows it and does not execute it.
              </p>
            </div>
          ) : null}
        </form>
      </CardContent>
    </Card>
  );
}
