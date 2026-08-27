"use client";

import { useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { LoadingState } from "@/components/ui/loading-state";
import { StatusPill } from "@/components/ui/status-pill";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type LogEntry = {
  id: string;
  kind: string;
  status: string;
  person_name: string | null;
  error: string | null;
  provider_status: number | null;
  attempt_count: number;
  activity_at?: string;
  due_at: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});
const actionLabels: Record<string, string> = {
  check_acceptances: "Check accepted invitations",
  send_invitation: "Send invitation",
  send_message: "Send message",
};

async function fetchLogs(): Promise<LogEntry[]> {
  const response = await fetch(apiUrl + "/logs", { cache: "no-store" });
  if (!response.ok) throw new Error("Logs could not be loaded.");
  return response.json();
}

export function LogsPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    void fetchLogs()
      .then((next) => {
        if (!active) return;
        setLogs(next);
        setError("");
      })
      .catch((loadError: Error) => {
        if (active) setError(loadError.message);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    const interval = window.setInterval(() => {
      void fetchLogs()
        .then((next) => {
          if (!active) return;
          setLogs(next);
          setError("");
        })
        .catch((loadError: Error) => {
          if (active) setError(loadError.message);
        });
    }, 3000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  return (
    <div className="mt-5 space-y-4">
      {error ? (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <div
        className="overflow-x-auto rounded-xl border"
        aria-label="Activity logs"
      >
        <Table className="min-w-[720px]">
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead className="px-3 font-normal">Time</TableHead>
              <TableHead className="px-3 font-normal">Action</TableHead>
              <TableHead className="px-3 font-normal">Person</TableHead>
              <TableHead className="px-3 font-normal">Status</TableHead>
              <TableHead className="px-3 font-normal">Details</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {logs.map((entry) => (
              <TableRow key={entry.id}>
                <TableCell className="px-3 text-xs text-muted-foreground tabular-nums">
                  {formatDate(
                    entry.activity_at ??
                      entry.completed_at ??
                      entry.started_at ??
                      entry.created_at,
                  )}
                </TableCell>
                <TableCell className="px-3">
                  {actionLabel(entry.kind)}
                </TableCell>
                <TableCell className="px-3 text-muted-foreground">
                  {entry.person_name ?? "All pending"}
                </TableCell>
                <TableCell className="px-3">
                  <StatusPill status={entry.status} />
                </TableCell>
                <TableCell className="px-3 text-xs text-muted-foreground">
                  <LogDetails entry={entry} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        {!isLoading && logs.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No activity yet.
          </p>
        ) : null}
        {isLoading ? (
          <LoadingState className="justify-center py-8">
            Loading logs...
          </LoadingState>
        ) : null}
      </div>
    </div>
  );
}

function LogDetails({ entry }: { entry: LogEntry }) {
  if (entry.error) {
    return (
      <details className="max-w-sm whitespace-normal">
        <summary className="cursor-pointer">Show error</summary>
        <p className="mt-1 text-destructive">{entry.error}</p>
      </details>
    );
  }
  if (entry.provider_status) return `LinkedIn HTTP ${entry.provider_status}`;
  if (entry.status === "queued") return `Due ${formatDate(entry.due_at)}`;
  if (entry.status === "running") return `Attempt ${entry.attempt_count}`;
  return "Completed";
}

function actionLabel(kind: string) {
  return actionLabels[kind] ?? kind.replaceAll("_", " ");
}

function formatDate(value: string) {
  return dateFormatter.format(new Date(value));
}
