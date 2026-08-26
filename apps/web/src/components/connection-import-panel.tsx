"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  CircleCheck,
  LoaderCircle,
  UploadCloud,
  X,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  FileUpload,
  FileUploadDropzone,
  FileUploadItem,
  FileUploadItemDelete,
  FileUploadItemMetadata,
  FileUploadItemPreview,
  FileUploadList,
} from "@/components/ui/file-upload";
import {
  Progress,
  ProgressLabel,
  ProgressValue,
} from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type PersonStatus =
  | "ready"
  | "invalid"
  | "duplicate"
  | "skipped"
  | "checking"
  | "pending"
  | "connected"
  | "sending"
  | "sent"
  | "accepted"
  | "failed";

export type DashboardSection = "send" | "history";

type ImportedPerson = {
  row_number: number;
  name: string;
  linkedin_url: string;
  public_id: string;
  status: PersonStatus;
  error: string | null;
  provider_status: number | null;
  sent_at: string | null;
  accepted_at: string | null;
  checked_at: string | null;
};

type ConnectionImport = {
  id: string;
  filename: string;
  status: "awaiting_approval" | "checking" | "sending" | "complete";
  people: ImportedPerson[];
  ready_count: number;
  sent_count: number;
  accepted_count: number;
  pending_count: number;
  connected_count: number;
  failed_count: number;
  skipped_count: number;
  total_count: number;
  checked_count: number;
  processed_count: number;
  progress_percent: number;
  created_at: string;
  approved_at: string | null;
  completed_at: string | null;
};

type AcceptanceRefreshResult = {
  checked_count: number;
  accepted_count: number;
  pending_count: number;
  checked_at: string;
};

type AcceptanceRequest = {
  state: string;
  work_item_id: string | null;
  due_at: string | null;
};

type WorkerStatus = {
  state: "idle" | "queued" | "working";
  current: string | null;
  last_finished_at: string | null;
  last_work_item_id: string | null;
  last_status: string | null;
  last_error: string | null;
  pending_invitations: number;
  accepted_invitations: number;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";
const dateFormatter = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
});

function upsertImport(
  current: ConnectionImport[],
  nextImport: ConnectionImport,
) {
  return [
    nextImport,
    ...current.filter((item) => item.id !== nextImport.id),
  ];
}

async function fetchImportHistory(): Promise<ConnectionImport[]> {
  const response = await fetch(apiUrl + "/connections/imports", {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("History could not be loaded.");
  }
  return response.json();
}

async function fetchWorkerStatus(): Promise<WorkerStatus> {
  const response = await fetch(apiUrl + "/automation/status", {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Worker status could not be loaded.");
  }
  return response.json();
}

function acceptanceResultFromStatus(
  status: WorkerStatus,
): AcceptanceRefreshResult {
  return {
    checked_count: status.pending_invitations + status.accepted_invitations,
    accepted_count: status.accepted_invitations,
    pending_count: status.pending_invitations,
    checked_at: status.last_finished_at ?? new Date().toISOString(),
  };
}

function isRunning(connectionImport: ConnectionImport | null) {
  return (
    connectionImport?.status === "checking" ||
    connectionImport?.status === "sending"
  );
}

function appear(reduced: boolean | null) {
  return {
    initial: reduced
      ? { opacity: 0 }
      : { opacity: 0, y: 12, filter: "blur(12px)" },
    animate: reduced
      ? { opacity: 1 }
      : { opacity: 1, y: 0, filter: "blur(0px)" },
    exit: reduced
      ? { opacity: 0 }
      : { opacity: 0, y: 8, filter: "blur(10px)" },
    transition: {
      duration: reduced ? 0.01 : 0.2,
      ease: "easeOut" as const,
    },
  };
}

export function ConnectionImportPanel({
  section,
}: {
  section: DashboardSection;
}) {
  const reducedMotion = useReducedMotion();
  const [file, setFile] = useState<File | null>(null);
  const [connectionImport, setConnectionImport] =
    useState<ConnectionImport | null>(null);
  const [history, setHistory] = useState<ConnectionImport[]>([]);
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());
  const [isUploading, setIsUploading] = useState(false);
  const [isCheckingAcceptance, setIsCheckingAcceptance] = useState(false);
  const [acceptanceActivity, setAcceptanceActivity] = useState("");
  const [acceptanceResult, setAcceptanceResult] =
    useState<AcceptanceRefreshResult | null>(null);
  const [error, setError] = useState("");
  const activeImportId = connectionImport?.id;
  const activeImportStatus = connectionImport?.status;

  useEffect(() => {
    let active = true;
    void fetchImportHistory()
      .then((imports) => {
        if (active) {
          setHistory(imports);
          setConnectionImport(
            imports.find((item) => isRunning(item)) ?? null,
          );
        }
      })
      .catch((historyError: Error) => {
        if (active) {
          setError(historyError.message);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (
      !activeImportId ||
      (activeImportStatus !== "checking" && activeImportStatus !== "sending")
    ) {
      return;
    }

    let active = true;
    const interval = window.setInterval(() => {
      void fetch(apiUrl + "/connections/import/" + activeImportId, {
        cache: "no-store",
      })
        .then((response) => {
          if (!response.ok) {
            throw new Error("Status could not be loaded.");
          }
          return response.json();
        })
        .then((data: ConnectionImport) => {
          if (active) {
            setConnectionImport(data);
            setHistory((current) => upsertImport(current, data));
          }
        })
        .catch(() => {
          if (active) {
            setError("Status could not be loaded.");
          }
        });
    }, 1000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [activeImportId, activeImportStatus]);

  async function importCsv(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      return;
    }

    setIsUploading(true);
    setError("");
    const formData = new FormData();
    formData.append("csv_file", file);

    try {
      const response = await fetch(apiUrl + "/connections/import", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "File could not be imported.");
      }
      const imported = data as ConnectionImport;
      setConnectionImport(imported);
      setSelectedRows(
        new Set(
          imported.people
            .filter((person) => person.status === "ready")
            .map((person) => person.row_number),
        ),
      );
      setHistory((current) =>
        upsertImport(current, imported),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "File could not be imported.",
      );
    } finally {
      setIsUploading(false);
    }
  }

  async function approveImport() {
    if (!connectionImport) {
      return;
    }

    const selectedReadyRows = connectionImport.people
      .filter(
        (person) =>
          person.status === "ready" && selectedRows.has(person.row_number),
      )
      .map((person) => person.row_number);
    if (selectedReadyRows.length === 0) {
      return;
    }

    setError("");
    try {
      const response = await fetch(
        apiUrl + "/connections/import/" + connectionImport.id + "/approve",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ row_numbers: selectedReadyRows }),
        },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Requests could not be started.");
      }
      setConnectionImport(data as ConnectionImport);
      setSelectedRows(new Set());
      setHistory((current) =>
        upsertImport(current, data as ConnectionImport),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Requests could not be started.",
      );
    }
  }

  async function refreshAcceptance() {
    setIsCheckingAcceptance(true);
    setAcceptanceResult(null);
    setError("");
    try {
      const response = await fetch(apiUrl + "/connections/acceptance/refresh", {
        method: "POST",
      });
      const data = (await response.json()) as AcceptanceRequest | { detail: string };
      if (!response.ok) {
        throw new Error(
          "detail" in data
            ? data.detail
            : "Accepted invitations could not be checked.",
        );
      }
      const request = data as AcceptanceRequest;
      if (!request.work_item_id) {
        const status = await fetchWorkerStatus();
        setAcceptanceResult(acceptanceResultFromStatus(status));
      } else {
        setAcceptanceActivity("Queued acceptance check.");
        while (true) {
          await new Promise((resolve) => window.setTimeout(resolve, 750));
          const status = await fetchWorkerStatus();
          setAcceptanceActivity(
            status.current ??
              (status.state === "queued"
                ? "Waiting for the local worker."
                : "Finishing acceptance check."),
          );
          if (status.last_work_item_id !== request.work_item_id) {
            continue;
          }
          if (status.last_status !== "succeeded") {
            throw new Error(status.last_error ?? "Acceptance check failed.");
          }
          setAcceptanceResult(acceptanceResultFromStatus(status));
          break;
        }
      }
      const imports = await fetchImportHistory();
      setHistory(imports);
      setConnectionImport((current) =>
        current ? imports.find((item) => item.id === current.id) ?? current : null,
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Accepted invitations could not be checked.",
      );
    } finally {
      setIsCheckingAcceptance(false);
      setAcceptanceActivity("");
    }
  }

  const activity = history
    .flatMap((item) =>
      item.people.map((person) => ({ importId: item.id, person })),
    )
    .filter(({ person }) =>
      ["pending", "connected", "sending", "sent", "failed", "accepted"].includes(
        person.status,
      ),
    )
    .slice(0, 100);
  const hasPendingAcceptance = activity.some(
    ({ person }) => person.status === "sent",
  );
  const sentInvitationCount = activity.filter(
    ({ person }) => person.status === "sent",
  ).length;
  const canSelectPeople = connectionImport?.status === "awaiting_approval";
  const readyPeople = canSelectPeople
    ? connectionImport.people.filter((person) => person.status === "ready")
    : [];
  const selectedReadyCount = readyPeople.filter((person) =>
    selectedRows.has(person.row_number),
  ).length;
  const allReadySelected =
    readyPeople.length > 0 && selectedReadyCount === readyPeople.length;
  const someReadySelected =
    selectedReadyCount > 0 && selectedReadyCount < readyPeople.length;

  return (
    <AnimatePresence mode="wait" initial={false}>
      {section === "send" ? (
        <motion.div key="send" {...appear(reducedMotion)} className="mt-5">
          <Card className="shadow-xl shadow-black/40">
            <CardContent className="space-y-4 px-4 sm:px-5">
              <form onSubmit={importCsv} className="space-y-3">
                <FileUpload
                  value={file ? [file] : []}
                  onValueChange={(files) => {
                    setFile(files[0] ?? null);
                    setConnectionImport(null);
                    setSelectedRows(new Set());
                    setError("");
                  }}
                  onFileReject={(_, message) => {
                    setError(
                      message === "File too large"
                        ? "File must be smaller than 2 MB."
                        : "Choose a CSV or spreadsheet.",
                    );
                  }}
                  accept=".csv,.xls,.xlsx,.xlsb,.xlsm,.ods,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.oasis.opendocument.spreadsheet"
                  maxFiles={1}
                  maxSize={2 * 1024 * 1024}
                  label="Contacts file"
                  disabled={isUploading || isRunning(connectionImport)}
                >
                  {!file ? (
                    <FileUploadDropzone className="min-h-36 rounded-xl border border-dashed bg-muted/20 px-4 py-8 hover:bg-muted/35 data-dragging:border-primary data-dragging:bg-muted/50">
                      <UploadCloud
                        className="size-6 text-muted-foreground"
                        aria-hidden="true"
                      />
                      <p className="text-center text-sm font-bold">
                        Drop CSV or spreadsheet
                      </p>
                      <p className="text-xs text-muted-foreground">2 MB max</p>
                    </FileUploadDropzone>
                  ) : null}

                  <FileUploadList>
                    {file ? (
                      <FileUploadItem
                        value={file}
                        className="rounded-xl bg-muted/20"
                      >
                        <FileUploadItemPreview className="size-10 rounded-lg [&>svg]:size-5" />
                        <FileUploadItemMetadata />
                        <FileUploadItemDelete
                          aria-label="Remove file"
                          className={buttonVariants({
                            variant: "outline",
                            size: "icon",
                          })}
                        >
                          <X aria-hidden="true" />
                        </FileUploadItemDelete>
                      </FileUploadItem>
                    ) : null}
                  </FileUploadList>
                </FileUpload>

                <Button
                  type="submit"
                  size="lg"
                  disabled={!file || isUploading || isRunning(connectionImport)}
                  className="h-11 w-full"
                >
                  Preview file
                </Button>
              </form>

              {error ? (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}

              {connectionImport ? (
                <motion.div {...appear(reducedMotion)} className="space-y-3">
                  <div
                    className="min-w-0"
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    {isRunning(connectionImport) ? (
                      <Progress
                        value={connectionImport.progress_percent}
                        aria-label={`${phaseLabel(connectionImport)} progress`}
                        className="gap-2"
                      >
                        <ProgressLabel>
                          {summary(connectionImport)}
                        </ProgressLabel>
                        <ProgressValue />
                      </Progress>
                    ) : (
                      <p className="pt-2 text-sm text-muted-foreground">
                        {summary(connectionImport)}
                      </p>
                    )}
                  </div>

                  <div
                    className="overflow-hidden rounded-xl border"
                    aria-label="Imported people"
                  >
                        <Table>
                          <TableHeader>
                            <TableRow className="bg-muted/40 hover:bg-muted/40">
                              {canSelectPeople ? (
                                <TableHead className="w-12 px-3">
                                  <Checkbox
                                    aria-label="Select all ready people"
                                    checked={allReadySelected}
                                    indeterminate={someReadySelected}
                                    disabled={readyPeople.length === 0}
                                    onCheckedChange={(checked) => {
                                      setSelectedRows((current) => {
                                        const next = new Set(current);
                                        for (const person of readyPeople) {
                                          if (checked) {
                                            next.add(person.row_number);
                                          } else {
                                            next.delete(person.row_number);
                                          }
                                        }
                                        return next;
                                      });
                                    }}
                                  />
                                </TableHead>
                              ) : null}
                              <TableHead className="px-3 font-bold">
                                Name
                              </TableHead>
                              <TableHead className="px-3 font-bold">
                                LinkedIn
                              </TableHead>
                              <TableHead className="px-3 font-bold">
                                Status
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {connectionImport.people.map((person) => (
                              <TableRow key={person.row_number}>
                                {canSelectPeople ? (
                                  <TableCell className="w-12 px-3">
                                    <Checkbox
                                      aria-label={`Select ${person.name}`}
                                      checked={selectedRows.has(
                                        person.row_number,
                                      )}
                                      disabled={person.status !== "ready"}
                                      onCheckedChange={(checked) => {
                                        setSelectedRows((current) => {
                                          const next = new Set(current);
                                          if (checked) {
                                            next.add(person.row_number);
                                          } else {
                                            next.delete(person.row_number);
                                          }
                                          return next;
                                        });
                                      }}
                                    />
                                  </TableCell>
                                ) : null}
                                <TableCell className="px-3">
                                  {person.name}
                                </TableCell>
                                <TableCell className="px-3 font-mono text-xs">
                                  {person.public_id || "-"}
                                </TableCell>
                                <TableCell className="px-3">
                                  <div className="flex max-w-sm flex-col items-start gap-1.5">
                                    <StatusBadge status={person.status} />
                                    {person.status === "failed" &&
                                    person.error ? (
                                      <span className="whitespace-normal text-xs leading-4 text-destructive">
                                        {person.error}
                                      </span>
                                    ) : null}
                                  </div>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                  </div>

                  {connectionImport.status === "awaiting_approval" &&
                  connectionImport.ready_count > 0 ? (
                    <Button
                      type="button"
                      size="lg"
                      onClick={approveImport}
                      disabled={selectedReadyCount === 0}
                      className="h-11 w-full sm:w-auto"
                    >
                      Send {selectedReadyCount} connection requests
                    </Button>
                  ) : null}
                </motion.div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>
      ) : (
        <motion.div key="history" {...appear(reducedMotion)} className="mt-5">
          <Card className="shadow-xl shadow-black/40">
            <CardContent className="space-y-3 px-4 sm:px-5">
              <div className="flex justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={refreshAcceptance}
                  disabled={!hasPendingAcceptance || isCheckingAcceptance}
                  aria-busy={isCheckingAcceptance}
                  className="min-h-11"
                >
                  Check accepted
                  {isCheckingAcceptance ? (
                    <LoaderCircle
                      className="animate-spin"
                      aria-hidden="true"
                    />
                  ) : null}
                </Button>
              </div>

              <AnimatePresence mode="wait" initial={false}>
                {isCheckingAcceptance ? (
                  <motion.p
                    key="checking"
                    {...appear(reducedMotion)}
                    role="status"
                    aria-live="polite"
                    aria-atomic="true"
                    className="text-sm text-muted-foreground"
                  >
                    {acceptanceActivity ||
                      `Checking ${sentInvitationCount} sent ${pluralize("invitation", sentInvitationCount)} against your LinkedIn connections.`}
                  </motion.p>
                ) : acceptanceResult ? (
                  <motion.div
                    key={acceptanceResult.checked_at}
                    {...appear(reducedMotion)}
                  >
                    <Alert
                      role="status"
                      aria-live="polite"
                      aria-atomic="true"
                      className="border-success/30 bg-success/10 text-success"
                    >
                      <CircleCheck aria-hidden="true" />
                      <AlertDescription className="text-success">
                        {acceptanceSummary(acceptanceResult)}
                      </AlertDescription>
                    </Alert>
                  </motion.div>
                ) : null}
              </AnimatePresence>

              {error ? (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : null}

              {activity.length > 0 ? (
                <div
                  className="overflow-hidden rounded-xl border"
                  aria-label="Invitation history"
                >
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/40 hover:bg-muted/40">
                        <TableHead className="px-3 font-bold">Name</TableHead>
                        <TableHead className="px-3 font-bold">Status</TableHead>
                        <TableHead className="px-3 text-right font-bold">
                          Sent
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {activity.map(({ importId, person }) => (
                        <TableRow key={`${importId}:${person.row_number}`}>
                          <TableCell className="px-3">{person.name}</TableCell>
                          <TableCell className="px-3">
                            <div className="flex max-w-sm flex-col items-start gap-1.5">
                              <StatusBadge status={person.status} />
                              {person.status === "failed" && person.error ? (
                                <span className="whitespace-normal text-xs leading-4 text-destructive">
                                  {person.error}
                                </span>
                              ) : null}
                            </div>
                          </TableCell>
                          <TableCell className="px-3 text-right text-xs text-muted-foreground tabular-nums">
                            {formatDate(person.sent_at)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No requests yet.
                </p>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function StatusBadge({ status }: { status: PersonStatus }) {
  if (status === "failed" || status === "invalid") {
    return <Badge variant="destructive">{status}</Badge>;
  }
  if (status === "accepted" || status === "connected") {
    return (
      <Badge className="border-success/30 bg-success/15 text-success">
        {status}
      </Badge>
    );
  }
  if (status === "checking" || status === "sending") {
    return (
      <Badge variant="secondary">
        <LoaderCircle className="animate-spin" aria-hidden="true" />
        {status}
      </Badge>
    );
  }
  if (status === "duplicate" || status === "skipped" || status === "pending") {
    return <Badge variant="outline">{status}</Badge>;
  }
  return <Badge variant="secondary">{status}</Badge>;
}

function summary(connectionImport: ConnectionImport) {
  if (connectionImport.status === "awaiting_approval") {
    return `${connectionImport.ready_count} ready, ${connectionImport.skipped_count} skipped.`;
  }
  if (connectionImport.status === "checking") {
    const current = connectionImport.people.find(
      (person) => person.status === "checking",
    );
    const position = Math.min(
      connectionImport.checked_count + (current ? 1 : 0),
      connectionImport.total_count,
    );
    return `Checking ${position} of ${connectionImport.total_count}${current ? ` · ${current.name}` : ""}`;
  }
  if (connectionImport.status === "sending") {
    const current = connectionImport.people.find(
      (person) => person.status === "sending",
    );
    const position = Math.min(
      connectionImport.processed_count + (current ? 1 : 0),
      connectionImport.total_count,
    );
    return `Sending ${position} of ${connectionImport.total_count}${current ? ` · ${current.name}` : ""}`;
  }
  return `Finished · ${connectionImport.sent_count} sent, ${connectionImport.pending_count} pending, ${connectionImport.connected_count} connected, ${connectionImport.failed_count} failed`;
}

function phaseLabel(connectionImport: ConnectionImport) {
  return connectionImport.status === "checking" ? "Checking" : "Sending";
}

function formatDate(value: string | null) {
  if (!value) {
    return "-";
  }
  return dateFormatter.format(new Date(value));
}

function acceptanceSummary(result: AcceptanceRefreshResult) {
  return `Finished. ${result.checked_count} ${pluralize("invitation", result.checked_count)} checked, ${result.accepted_count} newly accepted, ${result.pending_count} still pending.`;
}

function pluralize(noun: string, count: number) {
  return count === 1 ? noun : `${noun}s`;
}
