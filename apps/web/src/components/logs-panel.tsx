"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check, ChevronDown, Copy, Search, X } from "lucide-react";
import { Fragment, useEffect, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
import { appear } from "@/lib/motion";
import { cn } from "@/lib/utils";

type LogEntry = {
  id: string;
  kind: string;
  status: string;
  person_name: string | null;
  error: string | null;
  provider_status: number | null;
  attempt_count: number;
  activity_at: string;
  due_at: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

type LogPage = {
  items: LogEntry[];
  has_more: boolean;
  next_offset: number | null;
};

type CopyFeedback = {
  id: string;
  state: "copied" | "failed";
} | null;

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";
const pageSize = 50;
const maxVisibleLogs = 1000;
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
const statusOptions = [
  ["", "All statuses"],
  ["queued", "Queued"],
  ["running", "Running"],
  ["succeeded", "Succeeded"],
  ["failed", "Failed"],
  ["needs_review", "Needs review"],
  ["cancelled", "Cancelled"],
] as const;
const actionOptions = [
  ["", "All actions"],
  ["send_invitation", "Send invitation"],
  ["check_acceptances", "Check accepted invitations"],
  ["send_message", "Send message"],
] as const;
const fieldClassName =
  "h-8 rounded-lg border border-input bg-background px-2 text-sm font-normal text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50";

async function fetchLogs({
  limit = pageSize,
  offset = 0,
  search = "",
  status = "",
  kind = "",
  signal,
}: {
  limit?: number;
  offset?: number;
  search?: string;
  status?: string;
  kind?: string;
  signal?: AbortSignal;
} = {}): Promise<LogPage> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (search) params.set("search", search);
  if (status) params.set("status", status);
  if (kind) params.set("kind", kind);

  const response = await fetch(`${apiUrl}/logs?${params}`, {
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new Error("Logs could not be loaded.");
  return response.json();
}

export function LogsPanel() {
  const reducedMotion = useReducedMotion();
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [clock, setClock] = useState(() => new Date());
  const [copyFeedback, setCopyFeedback] = useState<CopyFeedback>(null);
  const [error, setError] = useState("");
  const logsRef = useRef<LogEntry[]>([]);
  const visibleLimitRef = useRef(pageSize);
  const filterGenerationRef = useRef(0);
  const expandedLogIdRef = useRef<string | null>(null);
  const isLoadingMoreRef = useRef(false);
  const isPollingRef = useRef(false);
  const loadMoreAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedSearch(search.trim());
    }, 250);
    return () => window.clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    expandedLogIdRef.current = expandedLogId;
  }, [expandedLogId]);

  useEffect(() => {
    const interval = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  useEffect(() => {
    return () => loadMoreAbortRef.current?.abort();
  }, []);

  useEffect(() => {
    let active = true;
    const filterGeneration = filterGenerationRef.current;
    const controller = new AbortController();
    const isCurrentFilter = () =>
      active && filterGeneration === filterGenerationRef.current;

    const loadVisibleLogs = async () => {
      try {
        const page = await fetchLogs({
          limit: visibleLimitRef.current,
          search: debouncedSearch,
          status: statusFilter,
          kind: actionFilter,
          signal: controller.signal,
        });
        if (!isCurrentFilter()) return;
        logsRef.current = page.items;
        setLogs(page.items);
        setHasMore(
          page.has_more && visibleLimitRef.current < maxVisibleLogs,
        );
        setLastUpdatedAt(new Date());
        setError("");
      } catch (loadError) {
        if (isCurrentFilter() && !isAbortError(loadError)) {
          setError((loadError as Error).message);
        }
      } finally {
        if (isCurrentFilter()) setIsLoading(false);
      }
    };

    void loadVisibleLogs();
    const interval = window.setInterval(() => {
      if (
        !isCurrentFilter() ||
        expandedLogIdRef.current ||
        isLoadingMoreRef.current ||
        isPollingRef.current
      ) {
        return;
      }
      isPollingRef.current = true;
      void fetchLogs({
        limit: visibleLimitRef.current,
        search: debouncedSearch,
        status: statusFilter,
        kind: actionFilter,
        signal: controller.signal,
      })
        .then((page) => {
          if (!isCurrentFilter()) return;
          logsRef.current = page.items;
          setLogs(page.items);
          setHasMore(
            page.has_more && visibleLimitRef.current < maxVisibleLogs,
          );
          setLastUpdatedAt(new Date());
          setError("");
        })
        .catch((loadError: unknown) => {
          if (isCurrentFilter() && !isAbortError(loadError)) {
            setError((loadError as Error).message);
          }
        })
        .finally(() => {
          isPollingRef.current = false;
        });
    }, 3000);

    return () => {
      active = false;
      controller.abort();
      isPollingRef.current = false;
      window.clearInterval(interval);
    };
  }, [actionFilter, debouncedSearch, statusFilter]);

  const hasFilters = Boolean(search || statusFilter || actionFilter);
  const liveMessage = liveUpdateLine({
    expanded: Boolean(expandedLogId),
    isLoading,
    lastUpdatedAt,
    now: clock,
  });

  async function loadMore() {
    loadMoreAbortRef.current?.abort();
    const controller = new AbortController();
    loadMoreAbortRef.current = controller;
    const filterGeneration = filterGenerationRef.current;
    const nextLimit = Math.min(
      visibleLimitRef.current + pageSize,
      maxVisibleLogs,
    );
    isLoadingMoreRef.current = true;
    setIsLoadingMore(true);
    try {
      const page = await fetchLogs({
        limit: nextLimit,
        search: debouncedSearch,
        status: statusFilter,
        kind: actionFilter,
        signal: controller.signal,
      });
      if (
        controller.signal.aborted ||
        filterGeneration !== filterGenerationRef.current
      ) {
        return;
      }
      visibleLimitRef.current = nextLimit;
      logsRef.current = page.items;
      setLogs(page.items);
      setHasMore(page.has_more && nextLimit < maxVisibleLogs);
      setLastUpdatedAt(new Date());
      setError("");
    } catch (loadError) {
      if (!isAbortError(loadError)) {
        setError((loadError as Error).message);
      }
    } finally {
      if (loadMoreAbortRef.current === controller) {
        loadMoreAbortRef.current = null;
        isLoadingMoreRef.current = false;
        setIsLoadingMore(false);
      }
    }
  }

  async function copyError(entry: LogEntry) {
    if (!entry.error) {
      setCopyFeedback({ id: entry.id, state: "failed" });
      return;
    }
    try {
      await navigator.clipboard.writeText(entry.error);
      setCopyFeedback({ id: entry.id, state: "copied" });
    } catch {
      setCopyFeedback({ id: entry.id, state: "failed" });
    }
  }

  function clearFilters() {
    setSearch("");
    setDebouncedSearch("");
    setStatusFilter("");
    setActionFilter("");
    beginFilterChange();
  }

  function beginFilterChange() {
    filterGenerationRef.current += 1;
    visibleLimitRef.current = pageSize;
    loadMoreAbortRef.current?.abort();
    loadMoreAbortRef.current = null;
    isLoadingMoreRef.current = false;
    setIsLoading(true);
    setIsLoadingMore(false);
    setExpandedLogId(null);
    setCopyFeedback(null);
  }

  return (
    <div className="mt-5 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <p aria-live="polite">{liveMessage}</p>
        <p>{hasMore ? `${logs.length} loaded` : `${logs.length} logs`}</p>
      </div>

      <div className="flex flex-wrap gap-2" aria-label="Filter activity logs">
        <label className="relative min-w-52 flex-1 sm:max-w-72">
          <span className="sr-only">Search people</span>
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <input
            className={cn(fieldClassName, "w-full pl-8")}
            type="search"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              beginFilterChange();
            }}
            placeholder="Search people"
          />
        </label>
        <label>
          <span className="sr-only">Filter by status</span>
          <select
            className={fieldClassName}
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              beginFilterChange();
            }}
          >
            {statusOptions.map(([value, label]) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span className="sr-only">Filter by action</span>
          <select
            className={fieldClassName}
            value={actionFilter}
            onChange={(event) => {
              setActionFilter(event.target.value);
              beginFilterChange();
            }}
          >
            {actionOptions.map(([value, label]) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <AnimatePresence initial={false}>
          {hasFilters ? (
            <motion.div {...appear(reducedMotion)}>
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                <X aria-hidden="true" />
                Clear
              </Button>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>

      <AnimatePresence initial={false}>
        {error ? (
          <motion.div {...appear(reducedMotion)}>
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="overflow-hidden rounded-xl border" aria-label="Activity logs">
        <Table className="min-w-[820px]">
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
            {logs.map((entry) => {
              const expanded = expandedLogId === entry.id;
              const detailsId = `log-details-${entry.id}`;
              return (
                <Fragment key={entry.id}>
                  <TableRow
                    className="cursor-pointer focus-visible:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
                    tabIndex={0}
                    aria-expanded={expanded}
                    aria-controls={detailsId}
                    onClick={() => setExpandedLogId(expanded ? null : entry.id)}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      setExpandedLogId(expanded ? null : entry.id);
                    }}
                  >
                    <TableCell className="px-3 text-xs text-muted-foreground tabular-nums">
                      {formatDate(entry.activity_at)}
                    </TableCell>
                    <TableCell className="px-3">{actionLabel(entry.kind)}</TableCell>
                    <TableCell className="px-3 text-muted-foreground">
                      {entry.person_name ?? "All pending"}
                    </TableCell>
                    <TableCell className="px-3">
                      <StatusPill status={entry.status} />
                    </TableCell>
                    <TableCell className="px-3 text-xs text-muted-foreground">
                      <span className="flex max-w-64 items-center justify-between gap-2">
                        <span className="truncate">{logSummary(entry)}</span>
                        <ChevronDown
                          className={cn(
                            "size-3.5 shrink-0 transition-transform",
                            expanded && "rotate-180",
                          )}
                          aria-hidden="true"
                        />
                      </span>
                    </TableCell>
                  </TableRow>
                  <AnimatePresence initial={false}>
                    {expanded ? (
                      <motion.tr
                        id={detailsId}
                        {...appear(reducedMotion)}
                        className="border-b bg-muted/20"
                      >
                        <TableCell colSpan={5} className="whitespace-normal p-0">
                          <ExpandedLog
                            entry={entry}
                            copyFeedback={copyFeedback}
                            onCopy={() => void copyError(entry)}
                          />
                        </TableCell>
                      </motion.tr>
                    ) : null}
                  </AnimatePresence>
                </Fragment>
              );
            })}
          </TableBody>
        </Table>

        <AnimatePresence initial={false}>
          {!isLoading && logs.length === 0 ? (
            <motion.p
              {...appear(reducedMotion)}
              className="py-8 text-center text-sm text-muted-foreground"
            >
              {hasFilters ? "No matching logs." : "No activity yet."}
            </motion.p>
          ) : null}
        </AnimatePresence>
        {isLoading ? (
          <LoadingState className="justify-center py-8">Loading logs...</LoadingState>
        ) : null}
      </div>

      <AnimatePresence initial={false}>
        {hasMore && !isLoading ? (
          <motion.div {...appear(reducedMotion)} className="flex justify-center pt-1">
            <Button
              variant="outline"
              size="sm"
              loading={isLoadingMore}
              onClick={() => void loadMore()}
            >
              Load more
            </Button>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

function ExpandedLog({
  entry,
  copyFeedback,
  onCopy,
}: {
  entry: LogEntry;
  copyFeedback: CopyFeedback;
  onCopy: () => void;
}) {
  const copied = copyFeedback?.id === entry.id && copyFeedback.state === "copied";
  const copyFailed =
    copyFeedback?.id === entry.id && copyFeedback.state === "failed";

  return (
    <div className="sticky left-0 w-[calc(100vw-2rem)] space-y-4 px-4 py-4 md:static md:w-auto">
      <dl className="grid gap-x-8 gap-y-3 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <Detail label="Log ID" value={entry.id} monospace />
        <Detail label="Attempt" value={String(entry.attempt_count)} />
        <Detail
          label="LinkedIn HTTP"
          value={entry.provider_status ? String(entry.provider_status) : "None"}
        />
        <Detail label="Due" value={formatOptionalDate(entry.due_at)} />
        <Detail label="Created" value={formatOptionalDate(entry.created_at)} />
        <Detail label="Started" value={formatOptionalDate(entry.started_at)} />
        <Detail label="Finished" value={formatOptionalDate(entry.completed_at)} />
        <Detail label="Activity" value={formatOptionalDate(entry.activity_at)} />
      </dl>

      {entry.error ? (
        <div className="border-t pt-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs text-muted-foreground">Exact error</p>
              <p className="mt-1 whitespace-pre-wrap break-words text-xs text-destructive">
                {entry.error}
              </p>
            </div>
            <Button variant="outline" size="xs" onClick={onCopy}>
              {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
              {copied ? "Copied" : "Copy error"}
            </Button>
          </div>
          {copyFailed ? (
            <p className="mt-2 text-xs text-destructive" role="alert">
              Error could not be copied.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Detail({
  label,
  value,
  monospace = false,
}: {
  label: string;
  value: string;
  monospace?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn("mt-0.5 break-words text-foreground", monospace && "font-mono")}>
        {value}
      </dd>
    </div>
  );
}

function isAbortError(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function logSummary(entry: LogEntry) {
  if (entry.error) return entry.error;
  if (entry.provider_status) return `LinkedIn HTTP ${entry.provider_status}`;
  if (entry.status === "queued") return `Due ${formatDate(entry.due_at)}`;
  if (entry.status === "running") return `Attempt ${entry.attempt_count}`;
  return "Completed";
}

function actionLabel(kind: string) {
  return actionLabels[kind] ?? kind.replaceAll("_", " ");
}

function liveUpdateLine({
  expanded,
  isLoading,
  lastUpdatedAt,
  now,
}: {
  expanded: boolean;
  isLoading: boolean;
  lastUpdatedAt: Date | null;
  now: Date;
}) {
  if (isLoading) return "Loading activity...";
  if (expanded) return "Live updates paused while details are open.";
  if (!lastUpdatedAt) return "Waiting for activity.";
  const seconds = Math.max(0, Math.floor((now.getTime() - lastUpdatedAt.getTime()) / 1000));
  if (seconds < 2) return "Updated just now.";
  return `Updated ${seconds}s ago.`;
}

function formatOptionalDate(value: string | null) {
  return value ? formatDate(value) : "Not set";
}

function formatDate(value: string) {
  return dateFormatter.format(new Date(value));
}
