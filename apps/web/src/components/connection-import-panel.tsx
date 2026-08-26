"use client";

import { motion, useReducedMotion } from "framer-motion";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";

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
    <motion.div {...appear(reducedMotion)} className="mt-6">
      <form onSubmit={importCsv} className="flex flex-col gap-3 sm:flex-row">
        <label className="sr-only" htmlFor="connections-csv">
          Clay CSV
        </label>
        <input
          id="connections-csv"
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setError("");
          }}
          className="min-h-11 min-w-0 flex-1 rounded-md border bg-card px-3 py-2 text-sm file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-medium"
        />
        <Button
          type="submit"
          size="lg"
          disabled={!file || isUploading || connectionImport?.status === "sending"}
          className="h-11 rounded-md px-4"
        >
          Preview CSV
        </Button>
      </form>

      {error ? (
        <p role="alert" className="mt-3 text-sm text-danger">
          {error}
        </p>
      ) : null}

      {connectionImport ? (
        <motion.div {...appear(reducedMotion)} className="mt-6">
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {summary(connectionImport)}
          </p>

          <div className="mt-3 overflow-x-auto border" aria-label="CSV people">
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">LinkedIn</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {connectionImport.people.map((person) => (
                  <tr key={person.row_number} className="border-b last:border-0">
                    <td className="px-3 py-2">{person.name}</td>
                    <td className="px-3 py-2 font-mono text-xs">
                      {person.public_id || "-"}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {person.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {connectionImport.status === "awaiting_approval" &&
          connectionImport.ready_count > 0 ? (
            <Button
              type="button"
              size="lg"
              onClick={approveImport}
              className="mt-4 h-11 rounded-md bg-linkedin px-4 text-white hover:bg-linkedin-hover"
            >
              Send {connectionImport.ready_count} connection requests
            </Button>
          ) : null}
        </motion.div>
      ) : null}
    </motion.div>
  );
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
