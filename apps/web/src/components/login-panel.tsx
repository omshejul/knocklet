"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { LoaderCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { DashboardShell } from "@/components/dashboard-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type ApiStatus = "idle" | "waiting" | "authenticated" | "failed";
type ViewStatus = ApiStatus | "loading" | "unavailable";

type LoginStatus = {
  status: ApiStatus;
  message: string;
  started_at: string | null;
  updated_at: string;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api";

async function fetchStatus(): Promise<ViewStatus> {
  try {
    const response = await fetch(apiUrl + "/auth/status", { cache: "no-store" });
    if (!response.ok) {
      return "unavailable";
    }
    const data = (await response.json()) as LoginStatus;
    return data.status;
  } catch {
    return "unavailable";
  }
}

function appear(reduced: boolean | null, delay = 0) {
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
      delay,
      ease: "easeOut" as const,
    },
  };
}

const viewCopy: Record<ViewStatus, string> = {
  loading: "Checking session...",
  idle: "Not signed in.",
  waiting: "Finish signing in in Chrome.",
  authenticated: "Signed in.",
  failed: "Login failed.",
  unavailable: "API unavailable.",
};

export function LoginPanel() {
  const reducedMotion = useReducedMotion();
  const [status, setStatus] = useState<ViewStatus>("loading");
  const [isStarting, setIsStarting] = useState(false);

  useEffect(() => {
    let active = true;
    void fetchStatus().then((nextStatus) => {
      if (active) {
        setStatus(nextStatus);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (status !== "waiting") {
      return;
    }
    let active = true;
    const interval = window.setInterval(() => {
      void fetchStatus().then((nextStatus) => {
        if (active) {
          setStatus(nextStatus);
        }
      });
    }, 1000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [status]);

  async function startLogin() {
    setIsStarting(true);
    try {
      const response = await fetch(apiUrl + "/auth/login", { method: "POST" });
      if (response.status !== 202 && response.status !== 409) {
        throw new Error("login request failed");
      }
      const data = (await response.json()) as LoginStatus;
      setStatus(data.status);
    } catch {
      setStatus("unavailable");
    } finally {
      setIsStarting(false);
    }
  }

  const isBusy = status === "loading" || status === "waiting" || isStarting;
  const isAuthenticated = status === "authenticated";

  if (isAuthenticated) {
    return <DashboardShell />;
  }

  return (
    <section
      aria-label="LinkedIn login"
      className="grid min-h-screen place-items-center px-5 py-12"
    >
      <div className="min-w-0 w-full max-w-sm">
        <h1 className="text-3xl font-normal tracking-tight">LinkedIn</h1>
        <Card className="mt-6 shadow-xl shadow-black/40">
          <CardContent className="px-4">
            <div className="min-h-6" aria-live="polite" aria-atomic="true">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div
                  key={status}
                  {...appear(reducedMotion)}
                  className="text-sm text-muted-foreground"
                >
                  {viewCopy[status]}
                </motion.div>
              </AnimatePresence>
            </div>

            <Button
              type="button"
              size="lg"
              disabled={isBusy}
              onClick={startLogin}
              aria-busy={isBusy}
              className="mt-5 h-11 w-full text-[0.95rem]"
            >
              <span>Log in with LinkedIn</span>
              {isBusy ? (
                <LoaderCircle className="animate-spin" aria-hidden="true" />
              ) : null}
            </Button>

            <p className="mt-3 text-xs text-muted-foreground">
              Opens Chrome on this Mac.
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
