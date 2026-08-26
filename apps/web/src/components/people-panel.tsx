"use client";

import { ExternalLink, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusPill } from "@/components/ui/status-pill";
import { cn } from "@/lib/utils";

type Person = {
  id: string;
  name: string;
  linkedin_url: string;
  public_id: string;
  invitation_status: string;
  invitation_error: string | null;
  invitation_provider_status: number | null;
  sent_at: string | null;
  accepted_at: string | null;
  checked_at: string | null;
  message_status: string;
  message_error: string | null;
  message_sent_at: string | null;
  last_activity_at: string;
};

type WorkerStatus = {
  state: "idle" | "queued" | "working";
  current: string | null;
  next_due_at: string | null;
  last_finished_at: string | null;
  last_work_item_id: string | null;
  last_status: string | null;
  last_error: string | null;
  last_acceptance_check_at: string | null;
  next_acceptance_check_at: string | null;
  pending_invitations: number;
  accepted_invitations: number;
};

type WorkItemStatus = {
  status: string;
  error: string | null;
};

type Filter = "all" | "pending" | "accepted" | "failed" | "needs_review";

const filters: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "pending", label: "Pending" },
  { id: "accepted", label: "Accepted" },
  { id: "failed", label: "Failed" },
  { id: "needs_review", label: "Needs review" },
];

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

async function fetchPeopleState() {
  const [peopleResponse, workerResponse] = await Promise.all([
    fetch(apiUrl + "/people", { cache: "no-store" }),
    fetch(apiUrl + "/automation/status", { cache: "no-store" }),
  ]);
  if (!peopleResponse.ok || !workerResponse.ok) {
    throw new Error("People could not be loaded.");
  }
  return {
    people: (await peopleResponse.json()) as Person[],
    worker: (await workerResponse.json()) as WorkerStatus,
  };
}

async function fetchWorkItem(workItemId: string): Promise<WorkItemStatus> {
  const response = await fetch(apiUrl + "/automation/work/" + workItemId, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Acceptance check status could not be loaded.");
  }
  return response.json();
}

export function PeoplePanel() {
  const [people, setPeople] = useState<Person[]>([]);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [requestedWorkId, setRequestedWorkId] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    const next = await fetchPeopleState();
    setPeople(next.people);
    setWorker(next.worker);
    return next.worker;
  }, []);

  useEffect(() => {
    let active = true;
    void fetchPeopleState()
      .then((next) => {
        if (!active) return;
        setPeople(next.people);
        setWorker(next.worker);
      })
      .catch((loadError: Error) => {
        if (active) setError(loadError.message);
      });
    const interval = window.setInterval(() => {
      void load()
        .then(async () => {
          if (!active || !requestedWorkId) return;
          const workItem = await fetchWorkItem(requestedWorkId);
          if (["queued", "running"].includes(workItem.status)) return;
          setRequestedWorkId(null);
          if (workItem.status === "succeeded") {
            setConfirmation("Acceptance check finished.");
          } else {
            setError(workItem.error ?? "Acceptance check failed.");
          }
        })
        .catch((loadError: Error) => {
          if (active) setError(loadError.message);
        });
    }, 1500);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [load, requestedWorkId]);

  const visiblePeople = useMemo(
    () => people.filter((person) => matchesFilter(person, filter)),
    [filter, people],
  );

  async function checkNow() {
    setConfirmation("");
    setError("");
    const response = await fetch(apiUrl + "/connections/acceptance/refresh", {
      method: "POST",
    });
    const data = (await response.json()) as {
      work_item_id: string | null;
      state: string;
      detail?: string;
    };
    if (!response.ok) {
      setError(data.detail ?? "Acceptance check could not be queued.");
      return;
    }
    if (!data.work_item_id) {
      setConfirmation("No pending invitations to check.");
      return;
    }
    setRequestedWorkId(data.work_item_id);
    await load();
  }

  const isChecking = requestedWorkId !== null;

  return (
    <Card className="mt-5 shadow-xl shadow-black/40">
      <CardContent className="space-y-4 px-4 sm:px-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {workerLine(worker, isChecking)}
          </p>
          <Button
            type="button"
            variant="outline"
            onClick={checkNow}
            disabled={isChecking || (worker?.pending_invitations ?? 0) === 0}
            aria-busy={isChecking}
            className="min-h-11"
          >
            Check now
            {isChecking ? (
              <LoaderCircle className="animate-spin" aria-hidden="true" />
            ) : null}
          </Button>
        </div>

        {confirmation ? (
          <p className="text-sm text-success" role="status" aria-live="polite">
            {confirmation}
          </p>
        ) : null}
        {error ? (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}

        <div className="flex flex-wrap gap-1" aria-label="Filter people">
          {filters.map((item) => (
            <Button
              key={item.id}
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setFilter(item.id)}
              aria-pressed={filter === item.id}
              className={cn(filter === item.id && "bg-muted text-foreground")}
            >
              {item.label}
            </Button>
          ))}
        </div>

        <div className="overflow-x-auto rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="px-3 font-bold">Name</TableHead>
                <TableHead className="px-3 font-bold">Invitation</TableHead>
                <TableHead className="px-3 font-bold">Message</TableHead>
                <TableHead className="px-3 text-right font-bold">
                  Last activity
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visiblePeople.map((person) => (
                <TableRow key={person.id}>
                  <TableCell className="px-3">
                    <a
                      href={person.linkedin_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 hover:underline"
                    >
                      {person.name}
                      <ExternalLink className="size-3" aria-hidden="true" />
                    </a>
                  </TableCell>
                  <TableCell className="px-3">
                    <State status={person.invitation_status} error={person.invitation_error} />
                  </TableCell>
                  <TableCell className="px-3">
                    <State status={person.message_status} error={person.message_error} />
                  </TableCell>
                  <TableCell className="px-3 text-right text-xs text-muted-foreground tabular-nums">
                    {formatDate(person.last_activity_at)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {visiblePeople.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No people.
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

function State({ status, error }: { status: string; error: string | null }) {
  return (
    <div className="flex flex-col items-start gap-1.5">
      <StatusPill status={status} />
      {error ? (
        <details className="max-w-xs text-xs text-muted-foreground">
          <summary className="cursor-pointer">Details</summary>
          <p className="mt-1 whitespace-normal text-destructive">{error}</p>
        </details>
      ) : null}
    </div>
  );
}

function matchesFilter(person: Person, filter: Filter) {
  if (filter === "all") return true;
  if (filter === "pending") {
    return ["queued", "checking", "sending", "pending"].includes(
      person.invitation_status,
    );
  }
  if (filter === "accepted") return person.invitation_status === "accepted";
  if (filter === "failed") {
    return person.invitation_status === "failed" || person.message_status === "failed";
  }
  return (
    person.invitation_status === "needs_review" ||
    person.message_status === "needs_review"
  );
}

function workerLine(worker: WorkerStatus | null, checking: boolean) {
  if (!worker) return "Loading activity...";
  if (worker.current) return worker.current;
  if (checking || worker.state === "queued") return "Waiting for the local worker.";
  const last = worker.last_acceptance_check_at
    ? `Last checked ${formatDate(worker.last_acceptance_check_at)}`
    : "Not checked yet";
  const next = worker.next_acceptance_check_at
    ? `Next check ${formatDate(worker.next_acceptance_check_at)}`
    : "No check scheduled";
  return `${last} · ${next}`;
}

function formatDate(value: string) {
  return dateFormatter.format(new Date(value));
}
