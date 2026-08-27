"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  CircleAlert,
  ExternalLink,
  MessageSquareText,
  MoreVertical,
  RotateCcw,
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
import { LoadingState } from "@/components/ui/loading-state";
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
import { appear } from "@/lib/motion";
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
  message_body: string | null;
  message_due_at: string | null;
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
  const reducedMotion = useReducedMotion();
  const [people, setPeople] = useState<Person[]>([]);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [requestedWorkId, setRequestedWorkId] = useState<string | null>(null);
  const [selectedPersonIds, setSelectedPersonIds] = useState<Set<string>>(
    new Set(),
  );
  const [deleteTargets, setDeleteTargets] = useState<Person[]>([]);
  const [reviewTarget, setReviewTarget] = useState<Person | null>(null);
  const [reviewOutcome, setReviewOutcome] = useState<
    "sent" | "not_sent" | null
  >(null);
  const [invitationActionIds, setInvitationActionIds] = useState<Set<string>>(
    new Set(),
  );
  const [messageActionIds, setMessageActionIds] = useState<Set<string>>(
    new Set(),
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isQueueingCheck, setIsQueueingCheck] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
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
      })
      .finally(() => {
        if (active) setIsLoading(false);
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
  const selectedMessagePeople = selectedPeople.filter(canQueueMessage);
  const selectedVisibleCount = visiblePeople.filter((person) =>
    selectedPersonIds.has(person.id),
  ).length;
  const allVisibleSelected =
    visiblePeople.length > 0 && selectedVisibleCount === visiblePeople.length;
  const someVisibleSelected =
    selectedVisibleCount > 0 && selectedVisibleCount < visiblePeople.length;

  async function checkNow() {
    setIsQueueingCheck(true);
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(apiUrl + "/connections/acceptance/refresh", {
        method: "POST",
      });
      const data = (await response.json()) as {
        work_item_id: string | null;
        state: string;
        detail?: string;
      };
      if (!response.ok) {
        throw new Error(data.detail ?? "Acceptance check could not be queued.");
      }
      if (!data.work_item_id) {
        setConfirmation("No pending invitations to check.");
        return;
      }
      setRequestedWorkId(data.work_item_id);
      await load();
    } catch (checkError) {
      setError(
        checkError instanceof Error
          ? checkError.message
          : "Acceptance check could not be queued.",
      );
    } finally {
      setIsQueueingCheck(false);
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

  async function queueMessages(targets: Person[]) {
    if (targets.length === 0) {
      setError("Select an accepted person who has no sent message.");
      return;
    }

    setMessageActionIds(new Set(targets.map((person) => person.id)));
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(apiUrl + "/people/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          person_ids: targets.map((person) => person.id),
        }),
      });
      const data = (await response.json()) as {
        queued_count?: number;
        detail?: string;
      };
      if (!response.ok) {
        throw new Error(data.detail ?? "Messages could not be queued.");
      }
      await load();
      const count = data.queued_count ?? targets.length;
      setConfirmation(
        `${count} ${count === 1 ? "message" : "messages"} queued.`,
      );
    } catch (messageError) {
      setError(
        messageError instanceof Error
          ? messageError.message
          : "Messages could not be queued.",
      );
    } finally {
      setMessageActionIds(new Set());
    }
  }

  async function retryInvitation(person: Person) {
    setInvitationActionIds(new Set([person.id]));
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(
        apiUrl + "/people/" + person.id + "/invitation/retry",
        { method: "POST" },
      );
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail ?? "Connection request could not be retried.");
      }
      await load();
      setConfirmation(`Connection request to ${person.name} queued.`);
    } catch (retryError) {
      setError(
        retryError instanceof Error
          ? retryError.message
          : "Connection request could not be retried.",
      );
    } finally {
      setInvitationActionIds(new Set());
    }
  }

  async function resolveReview(outcome: "sent" | "not_sent") {
    if (!reviewTarget) return;
    const person = reviewTarget;
    const kind = reviewKind(person);
    setReviewOutcome(outcome);
    setConfirmation("");
    setError("");
    try {
      const response = await fetch(
        apiUrl + "/people/" + person.id + "/review",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ outcome }),
        },
      );
      const data = (await response.json()) as { detail?: string };
      if (!response.ok) {
        throw new Error(data.detail ?? `${kindLabel(kind)} could not be updated.`);
      }
      await load();
      setReviewTarget(null);
      setConfirmation(
        outcome === "sent"
          ? `${person.name}'s ${kindLabel(kind)} marked as sent.`
          : `${person.name}'s ${kindLabel(kind)} queued again.`,
      );
    } catch (reviewError) {
      setReviewTarget(null);
      setError(
        reviewError instanceof Error
          ? reviewError.message
          : `${kindLabel(kind)} could not be updated.`,
      );
    } finally {
      setReviewOutcome(null);
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

  const isChecking = isQueueingCheck || requestedWorkId !== null;

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
            disabled={(worker?.pending_invitations ?? 0) === 0}
            loading={isChecking}
            className="min-h-11"
          >
            Check now
          </Button>
        </div>

        <AnimatePresence mode="wait" initial={false}>
          {confirmation ? (
            <motion.p
              key={confirmation}
              {...appear(reducedMotion)}
              className="text-sm text-success"
              role="status"
              aria-live="polite"
            >
              {confirmation}
            </motion.p>
          ) : error ? (
            <motion.div key={error} {...appear(reducedMotion)}>
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            </motion.div>
          ) : null}
        </AnimatePresence>

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
          <div className="flex flex-wrap gap-2">
            {selectedMessagePeople.length > 0 ? (
              <Button
                type="button"
                size="sm"
                onClick={() => void queueMessages(selectedMessagePeople)}
                loading={selectedMessagePeople.some((person) =>
                  messageActionIds.has(person.id),
                )}
              >
                {selectedMessagePeople.length === 1 &&
                selectedMessagePeople[0].message_status === "failed" ? (
                  <RotateCcw aria-hidden="true" />
                ) : (
                  <MessageSquareText aria-hidden="true" />
                )}
                {bulkMessageLabel(selectedMessagePeople)}
              </Button>
            ) : null}
            {selectedPeople.length > 0 ? (
              <Button
                type="button"
                size="sm"
                variant="destructive"
                disabled={
                  messageActionIds.size > 0 || invitationActionIds.size > 0
                }
                onClick={() => setDeleteTargets(selectedPeople)}
              >
                <Trash2 aria-hidden="true" />
                Delete selected ({selectedPeople.length})
              </Button>
            ) : null}
          </div>
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
              {visiblePeople.map((person) => (
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
                      loading={invitationActionIds.has(person.id)}
                      loadingLabel="Queueing request..."
                    />
                  </TableCell>
                  <TableCell className="px-3">
                    <State
                      status={person.message_status}
                      error={person.message_error}
                      body={person.message_body}
                      dueAt={person.message_due_at}
                      sentAt={person.message_sent_at}
                      loading={messageActionIds.has(person.id)}
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
                      <DropdownMenuContent align="end" className="w-36">
                        {person.invitation_status === "failed" ? (
                          <DropdownMenuItem
                            disabled={
                              messageActionIds.size > 0 ||
                              invitationActionIds.size > 0
                            }
                            onClick={() => void retryInvitation(person)}
                          >
                            <RotateCcw aria-hidden="true" />
                            Retry request
                          </DropdownMenuItem>
                        ) : null}
                        {hasReviewAction(person) ? (
                          <DropdownMenuItem
                            disabled={
                              messageActionIds.size > 0 ||
                              invitationActionIds.size > 0
                            }
                            onClick={() => setReviewTarget(person)}
                          >
                            <CircleAlert aria-hidden="true" />
                            Verify delivery
                          </DropdownMenuItem>
                        ) : null}
                        {canQueueMessage(person) ? (
                          <DropdownMenuItem
                            disabled={
                              messageActionIds.size > 0 ||
                              invitationActionIds.size > 0
                            }
                            onClick={() => void queueMessages([person])}
                          >
                            {person.message_status === "failed" ? (
                              <RotateCcw aria-hidden="true" />
                            ) : (
                              <MessageSquareText aria-hidden="true" />
                            )}
                            {person.message_status === "failed"
                              ? "Retry message"
                              : "Send message"}
                          </DropdownMenuItem>
                        ) : null}
                        <DropdownMenuItem
                          variant="destructive"
                          disabled={
                            messageActionIds.size > 0 ||
                            invitationActionIds.size > 0
                          }
                          onClick={() => setDeleteTargets([person])}
                        >
                          <Trash2 aria-hidden="true" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {isLoading ? (
            <LoadingState className="justify-center py-8">
              Loading people...
            </LoadingState>
          ) : visiblePeople.length === 0 ? (
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
              loading={isDeleting}
              onClick={() => void deletePerson()}
            >
              {deleteTargets.length === 1
                ? "Delete person"
                : `Delete ${deleteTargets.length} people`}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog
        open={reviewTarget !== null}
        onOpenChange={(open) => {
          if (!open && reviewOutcome === null) setReviewTarget(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {reviewTarget
                ? `Verify ${kindLabel(reviewKind(reviewTarget))} for ${reviewTarget.name}`
                : "Verify delivery"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              LinkedIn did not confirm whether this was sent. Check LinkedIn,
              then choose the matching result. Retrying without checking can
              create a duplicate.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={reviewOutcome !== null}>
              Cancel
            </AlertDialogCancel>
            <Button
              type="button"
              variant="outline"
              loading={reviewOutcome === "sent"}
              disabled={reviewOutcome === "not_sent"}
              onClick={() => void resolveReview("sent")}
            >
              It was sent
            </Button>
            <Button
              type="button"
              loading={reviewOutcome === "not_sent"}
              disabled={reviewOutcome === "sent"}
              onClick={() => void resolveReview("not_sent")}
            >
              It was not sent, retry
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}

function State({
  status,
  error,
  body = null,
  dueAt = null,
  sentAt = null,
  loading = false,
  loadingLabel = "Queueing message...",
}: {
  status: string;
  error: string | null;
  body?: string | null;
  dueAt?: string | null;
  sentAt?: string | null;
  loading?: boolean;
  loadingLabel?: string;
}) {
  if (loading) {
    return <LoadingState>{loadingLabel}</LoadingState>;
  }
  const timing =
    status === "queued" && dueAt
      ? `Sends ${formatDate(dueAt)}`
      : status === "sent" && sentAt
        ? `Sent ${formatDate(sentAt)}`
        : "";
  return (
    <div className="flex flex-col items-start gap-1.5">
      <StatusPill status={status} />
      {timing ? (
        <span className="text-xs text-muted-foreground tabular-nums">
          {timing}
        </span>
      ) : null}
      {body ? (
        <details className="max-w-xs text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            {status === "sent" ? "View message" : "Preview message"}
          </summary>
          <p className="mt-1 whitespace-pre-wrap text-foreground">{body}</p>
        </details>
      ) : null}
      {error ? (
        <details className="max-w-xs text-xs text-muted-foreground">
          <summary className="cursor-pointer">Details</summary>
          <p className="mt-1 whitespace-normal text-destructive">{error}</p>
        </details>
      ) : null}
    </div>
  );
}

function hasReviewAction(person: Person) {
  return (
    person.invitation_status === "needs_review" ||
    person.message_status === "needs_review"
  );
}

function reviewKind(person: Person): "invitation" | "message" {
  return person.message_status === "needs_review" ? "message" : "invitation";
}

function kindLabel(kind: "invitation" | "message") {
  return kind === "invitation" ? "connection request" : "message";
}

function canQueueMessage(person: Person) {
  return (
    person.invitation_status === "accepted" &&
    ["not_scheduled", "failed"].includes(person.message_status)
  );
}

function bulkMessageLabel(people: Person[]) {
  if (people.length === 1) {
    return people[0].message_status === "failed"
      ? "Retry message"
      : "Send message";
  }
  return people.some((person) => person.message_status === "failed")
    ? `Send or retry messages (${people.length})`
    : `Send messages (${people.length})`;
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
