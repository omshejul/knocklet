"use client";

import { motion, useReducedMotion } from "framer-motion";
import { UploadCloud, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
  | "sending"
  | "sent"
  | "failed";

type ImportedPerson = {
  row_number: number;
  name: string;
  linkedin_url: string;
  public_id: string;
  status: PersonStatus;
  error: string | null;
};

type ConnectionImport = {
  id: string;
  filename: string;
  status: "awaiting_approval" | "sending" | "complete";
  people: ImportedPerson[];
  ready_count: number;
  sent_count: number;
  failed_count: number;
  skipped_count: number;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

function appear(reduced: boolean | null) {
  return {
    initial: reduced
      ? { opacity: 0 }
      : { opacity: 0, y: 12, filter: "blur(12px)" },
    animate: reduced
      ? { opacity: 1 }
      : { opacity: 1, y: 0, filter: "blur(0px)" },
    transition: {
      duration: reduced ? 0.01 : 0.2,
      ease: "easeOut" as const,
    },
  };
}

export function ConnectionImportPanel() {
  const reducedMotion = useReducedMotion();
  const [file, setFile] = useState<File | null>(null);
  const [connectionImport, setConnectionImport] =
    useState<ConnectionImport | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (connectionImport?.status !== "sending") {
      return;
    }

    let active = true;
    const interval = window.setInterval(() => {
      void fetch(apiUrl + "/connections/import/" + connectionImport.id, {
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
  }, [connectionImport?.id, connectionImport?.status]);

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
        throw new Error(data.detail || "CSV could not be imported.");
      }
      setConnectionImport(data as ConnectionImport);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "CSV could not be imported.",
      );
    } finally {
      setIsUploading(false);
    }
  }

  async function approveImport() {
    if (!connectionImport) {
      return;
    }

    setError("");
    try {
      const response = await fetch(
        apiUrl + "/connections/import/" + connectionImport.id + "/approve",
        { method: "POST" },
      );
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Requests could not be started.");
      }
      setConnectionImport(data as ConnectionImport);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Requests could not be started.",
      );
    }
  }

  return (
    <motion.div {...appear(reducedMotion)} className="mt-5">
      <Card className="shadow-xl shadow-black/40">
        <CardContent className="space-y-4 px-4 sm:px-5">
          <form onSubmit={importCsv} className="space-y-3">
            <FileUpload
              value={file ? [file] : []}
              onValueChange={(files) => {
                setFile(files[0] ?? null);
                setConnectionImport(null);
                setError("");
              }}
              onFileReject={(_, message) => {
                setError(
                  message === "File too large"
                    ? "CSV must be smaller than 2 MB."
                    : "Choose a CSV file.",
                );
              }}
              accept=".csv,text/csv"
              maxFiles={1}
              maxSize={2 * 1024 * 1024}
              label="Clay CSV"
              disabled={
                isUploading || connectionImport?.status === "sending"
              }
            >
              {!file ? (
                <FileUploadDropzone className="min-h-36 rounded-xl border border-dashed bg-muted/20 px-4 py-8 hover:bg-muted/35 data-dragging:border-primary data-dragging:bg-muted/50">
                  <UploadCloud className="size-6 text-muted-foreground" aria-hidden="true" />
                  <p className="text-center text-sm font-bold">
                    Drop CSV or click to browse
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
                      aria-label="Remove CSV"
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
              disabled={
                !file || isUploading || connectionImport?.status === "sending"
              }
              className="h-11 w-full"
            >
              Preview CSV
            </Button>
          </form>

          {error ? (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          {connectionImport ? (
            <motion.div {...appear(reducedMotion)} className="space-y-3">
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {summary(connectionImport)}
              </p>

              <div
                className="overflow-hidden rounded-xl border"
                aria-label="CSV people"
              >
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/40 hover:bg-muted/40">
                      <TableHead className="px-3 font-bold">Name</TableHead>
                      <TableHead className="px-3 font-bold">LinkedIn</TableHead>
                      <TableHead className="px-3 font-bold">Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {connectionImport.people.map((person) => (
                      <TableRow key={person.row_number}>
                        <TableCell className="px-3">{person.name}</TableCell>
                        <TableCell className="px-3 font-mono text-xs">
                          {person.public_id || "-"}
                        </TableCell>
                        <TableCell className="px-3">
                          <StatusBadge status={person.status} />
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
                  className="h-11 w-full sm:w-auto"
                >
                  Send {connectionImport.ready_count} connection requests
                </Button>
              ) : null}
            </motion.div>
          ) : null}
        </CardContent>
      </Card>
    </motion.div>
  );
}

function StatusBadge({ status }: { status: PersonStatus }) {
  if (status === "failed" || status === "invalid") {
    return <Badge variant="destructive">{status}</Badge>;
  }
  if (status === "sent") {
    return (
      <Badge className="border-success/30 bg-success/15 text-success">
        {status}
      </Badge>
    );
  }
  if (status === "duplicate") {
    return <Badge variant="outline">{status}</Badge>;
  }
  return <Badge variant="secondary">{status}</Badge>;
}

function summary(connectionImport: ConnectionImport) {
  if (connectionImport.status === "awaiting_approval") {
    return `${connectionImport.ready_count} ready, ${connectionImport.skipped_count} skipped.`;
  }
  if (connectionImport.status === "sending") {
    return `Sending. ${connectionImport.sent_count} sent, ${connectionImport.failed_count} failed.`;
  }
  return `${connectionImport.sent_count} sent, ${connectionImport.failed_count} failed, ${connectionImport.skipped_count} skipped.`;
}
