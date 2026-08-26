"use client";

import {
  ExternalLink,
  LoaderCircle,
  MoreVertical,
  RefreshCw,
  Send,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusPill } from "@/components/ui/status-pill";
import { useRangeSelection } from "@/hooks/use-range-selection";
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
  available_action: string | null;
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

type ProcessPeopleResult = {
  requested_count: number;
  invitation_count: number;
  message_count: number;
  check_count: number;
  skipped_count: number;
  acceptance_work_item_id: string | null;
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
  const [selectedPersonIds, setSelectedPersonIds] = useState<Set<string>>(
    new Set(),
  );
  const [deleteTargets, setDeleteTargets] = useState<Person[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
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
  const {
    resetRangeAnchor: resetPersonRangeAnchor,
    toggleRangeSelection: togglePersonRange,
  } = useRangeSelection(
    visiblePeople.map((person) => person.id),
    setSelectedPersonIds,
  );
  const selectedPeople = useMemo(
    () => people.filter((person) => selectedPersonIds.has(person.id)),
    [people, selectedPersonIds],
  );
  const selectedVisibleCount = visiblePeople.filter((person) =>
    selectedPersonIds.has(person.id),
  ).length;
  const allVisibleSelected =
    visiblePeople.length > 0 && selectedVisibleCount === visiblePeople.length;
  const someVisibleSelected =
    selectedVisibleCount > 0 && selectedVisibleCount < visiblePeople.length;

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

  async function processPeople(targets: Person[]) {
    const eligibleTargets = targets.filter((person) => personAction(person));
    if (eligibleTargets.length === 0) {
      setError("No selected people have an available action.");
      return;
    }

    setIsProcessing(true);
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(apiUrl + "/people/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_ids: eligibleTargets.map((person) => person.id),
        }),
      });
      const data = (await response.json()) as ProcessPeopleResult & {
        detail?: string;
      };
      if (!response.ok) {
        throw new Error(data.detail ?? "People could not be processed.");
      }

      setConfirmation(processSummary(data));
      setSelectedPersonIds((current) => {
        const next = new Set(current);
        for (const person of eligibleTargets) next.delete(person.id);
        return next;
      });
      if (data.acceptance_work_item_id) {
        setRequestedWorkId(data.acceptance_work_item_id);
      }
      await load();
    } catch (processError) {
      setError(
        processError instanceof Error
          ? processError.message
          : "People could not be processed.",
      );
    } finally {
      setIsProcessing(false);
    }
  }

  async function deletePerson() {
    if (deleteTargets.length === 0) return;

    const peopleToDelete = deleteTargets;
    setIsDeleting(true);
    setConfirmation("");
    setError("");
    const results = await Promise.all(
      peopleToDelete.map(async (person) => {
        try {
          const response = await fetch(apiUrl + "/people/" + person.id, {
            method: "DELETE",
          });
          if (!response.ok) {
            const data = (await response.json().catch(() => ({}))) as {
              detail?: string;
            };
            throw new Error(data.detail ?? "Person could not be deleted.");
          }
          return { person, error: null };
        } catch (deleteError) {
          return {
            person,
            error:
              deleteError instanceof Error
                ? deleteError.message
                : "Person could not be deleted.",
          };
        }
      }),
    );

    const deletedIds = new Set(
      results.filter((result) => !result.error).map((result) => result.person.id),
    );
    const failures = results.filter((result) => result.error);
    if (deletedIds.size > 0) {
      setPeople((current) =>
        current.filter((person) => !deletedIds.has(person.id)),
      );
      setSelectedPersonIds((current) => {
        const next = new Set(current);
        for (const id of deletedIds) next.delete(id);
        return next;
      });
    }
    setDeleteTargets([]);
    setIsDeleting(false);

    if (failures.length > 0) {
      const firstFailure = failures[0];
      setError(
        `${failures.length} ${personWord(failures.length)} could not be deleted. ${firstFailure.person.name}: ${firstFailure.error}`,
      );
    } else {
      setConfirmation(
        `${deletedIds.size} ${personWord(deletedIds.size)} deleted.`,
      );
    }
  }

  function toggleVisiblePeople(checked: boolean) {
    setSelectedPersonIds((current) => {
      const next = new Set(current);
      for (const person of visiblePeople) {
        if (checked) {
          next.add(person.id);
        } else {
          next.delete(person.id);
        }
      }
      return next;
    });
    resetPersonRangeAnchor();
  }

  const isChecking = requestedWorkId !== null;
  const actionableSelectedPeople = selectedPeople.filter((person) =>
    personAction(person),
  );

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

        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-1" aria-label="Filter people">
            {filters.map((item) => (
              <Button
                key={item.id}
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  setFilter(item.id);
                  resetPersonRangeAnchor();
                }}
                aria-pressed={filter === item.id}
                className={cn(filter === item.id && "bg-muted text-foreground")}
              >
                {item.label}
              </Button>
            ))}
          </div>
          {selectedPeople.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {actionableSelectedPeople.length > 0 ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={isProcessing}
                  aria-busy={isProcessing}
                  onClick={() => void processPeople(actionableSelectedPeople)}
                >
                  {isProcessing ? (
                    <LoaderCircle className="animate-spin" aria-hidden="true" />
                  ) : (
                    <RefreshCw aria-hidden="true" />
                  )}
                  {bulkActionLabel(actionableSelectedPeople)}
                </Button>
              ) : null}
              <Button
                type="button"
                size="sm"
                variant="destructive"
                onClick={() => setDeleteTargets(selectedPeople)}
              >
                <Trash2 aria-hidden="true" />
                Delete selected ({selectedPeople.length})
              </Button>
            </div>
          ) : null}
        </div>

        <div className="overflow-x-auto rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-12 px-3">
                  <Checkbox
                    aria-label="Select all visible people"
                    checked={allVisibleSelected}
                    indeterminate={someVisibleSelected}
                    disabled={visiblePeople.length === 0}
                    onCheckedChange={toggleVisiblePeople}
                  />
                </TableHead>
                <TableHead className="px-3 font-normal">Name</TableHead>
                <TableHead className="px-3 font-normal">Invitation</TableHead>
                <TableHead className="px-3 font-normal">Message</TableHead>
                <TableHead className="px-3 text-right font-normal">
                  Last activity
                </TableHead>
                <TableHead className="w-12 px-2">
                  <span className="sr-only">Actions</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visiblePeople.map((person) => {
                const action = personAction(person);
                const ActionIcon = action?.icon;
                return (
                  <TableRow
                    key={person.id}
                    data-state={
                      selectedPersonIds.has(person.id) ? "selected" : undefined
                    }
                  >
                    <TableCell className="w-12 px-3">
                      <Checkbox
                        aria-label={`Select ${person.name}`}
                        checked={selectedPersonIds.has(person.id)}
                        onCheckedChange={(checked, eventDetails) => {
                          togglePersonRange(
                            person.id,
                            Boolean(checked),
                            eventDetails.event,
                          );
                        }}
                      />
                    </TableCell>
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
                      <State
                        status={person.invitation_status}
                        error={person.invitation_error}
                      />
                    </TableCell>
                    <TableCell className="px-3">
                      <State
                        status={person.message_status}
                        error={person.message_error}
                      />
                    </TableCell>
                    <TableCell className="px-3 text-right text-xs text-muted-foreground tabular-nums">
                      {formatDate(person.last_activity_at)}
                    </TableCell>
                    <TableCell className="px-2 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger
                          render={
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              aria-label={`Actions for ${person.name}`}
                            />
                          }
                        >
                          <MoreVertical aria-hidden="true" />
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-40">
                          {action && ActionIcon ? (
                            <DropdownMenuItem
                              disabled={isProcessing}
                              onClick={() => void processPeople([person])}
                            >
                              <ActionIcon aria-hidden="true" />
                              {action.label}
                            </DropdownMenuItem>
                          ) : null}
                          <DropdownMenuItem
                            variant="destructive"
                            onClick={() => setDeleteTargets([person])}
                          >
                            <Trash2 aria-hidden="true" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          {visiblePeople.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No people.
            </p>
          ) : null}
        </div>
      </CardContent>

      <AlertDialog
        open={deleteTargets.length > 0}
        onOpenChange={(open) => {
          if (!open && !isDeleting) setDeleteTargets([]);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {deleteTargets.length === 1
                ? `Delete ${deleteTargets[0].name}?`
                : `Delete ${deleteTargets.length} people?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              This removes their local invitation, message, and activity. Past
              import rows stay. Nothing changes on LinkedIn.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isDeleting}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={isDeleting}
              aria-busy={isDeleting}
              onClick={() => void deletePerson()}
            >
              {deleteTargets.length === 1
                ? "Delete person"
                : `Delete ${deleteTargets.length} people`}
              {isDeleting ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : null}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
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

function personWord(count: number) {
  return count === 1 ? "person" : "people";
}

function personAction(person: Person) {
  if (person.available_action === "send_request") {
    return { id: "send", label: "Send request", icon: Send } as const;
  }
  if (person.available_action === "retry_request") {
    return { id: "retry", label: "Retry request", icon: RefreshCw } as const;
  }
  if (person.available_action === "check_status") {
    return { id: "check", label: "Check status", icon: RefreshCw } as const;
  }
  if (person.available_action === "retry_message") {
    return { id: "retry", label: "Retry message", icon: RefreshCw } as const;
  }
  return null;
}

function bulkActionLabel(people: Person[]) {
  const actions = new Set(people.map((person) => personAction(person)?.id));
  const count = people.length;
  if (actions.size === 1 && actions.has("send")) {
    return `Send selected (${count})`;
  }
  if (actions.size === 1 && actions.has("retry")) {
    return `Retry selected (${count})`;
  }
  if (actions.size === 1 && actions.has("check")) {
    return `Check selected (${count})`;
  }
  return `Process eligible (${count})`;
}

function processSummary(result: ProcessPeopleResult) {
  const parts: string[] = [];
  if (result.invitation_count) {
    const noun = result.invitation_count === 1 ? "request" : "requests";
    parts.push(`${result.invitation_count} connection ${noun} queued`);
  }
  if (result.message_count) {
    const noun = result.message_count === 1 ? "message" : "messages";
    parts.push(`${result.message_count} ${noun} queued`);
  }
  if (result.check_count) {
    const noun = result.check_count === 1 ? "request" : "requests";
    parts.push(`${result.check_count} pending ${noun} queued for checking`);
  }
  if (result.skipped_count) {
    parts.push(`${result.skipped_count} skipped`);
  }
  return parts.length ? `${parts.join(", ")}.` : "No actions were queued.";
}
