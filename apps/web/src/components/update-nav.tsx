"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Download, RefreshCw, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { appear } from "@/lib/motion";

type UpdateStatus =
  | "idle"
  | "checking"
  | "available"
  | "downloading"
  | "downloaded"
  | "installing"
  | "up-to-date"
  | "error"
  | "unavailable";

type UpdateState = {
  status: UpdateStatus;
  currentVersion: string;
  availableVersion: string | null;
  progress: number | null;
  error: string | null;
};

type UpdateBridge = {
  check: () => Promise<UpdateState>;
  download: () => Promise<UpdateState>;
  getState: () => Promise<UpdateState>;
  install: () => Promise<UpdateState>;
  subscribe: (listener: (state: UpdateState) => void) => () => void;
};

declare global {
  interface Window {
    knockletUpdates?: UpdateBridge;
  }
}

export function UpdateNav({
  collapsed = false,
  className,
}: {
  collapsed?: boolean;
  className?: string;
}) {
  const reducedMotion = useReducedMotion();
  const [state, setState] = useState<UpdateState | null>(null);
  const [isActing, setIsActing] = useState(false);

  useEffect(() => {
    const updates = window.knockletUpdates;
    if (!updates) return;
    let active = true;
    const unsubscribe = updates.subscribe((nextState) => {
      if (active) setState(nextState);
    });
    void updates.getState().then(setState).catch((error: Error) => {
      if (!active) return;
      setState({
        status: "error",
        currentVersion: "unknown",
        availableVersion: null,
        progress: null,
        error: error.message,
      });
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  if (!state) return null;

  const action = updateAction(state);
  const disabled =
    isActing ||
    ["checking", "downloading", "installing", "unavailable"].includes(
      state.status,
    );

  async function performAction() {
    const updates = window.knockletUpdates;
    if (!updates) {
      setState((current) =>
        current ? { ...current, status: "error", error: "Update service unavailable." } : current,
      );
      return;
    }
    setIsActing(true);
    if (action.id === "install") {
      setState((current) =>
        current
          ? { ...current, status: "installing", progress: 100, error: null }
          : current,
      );
    }
    try {
      const nextState = await updates[action.id]();
      setState(nextState);
    } catch (error) {
      setState((current) =>
        current
          ? {
              ...current,
              status: "error",
              error: error instanceof Error ? error.message : String(error),
            }
          : current,
      );
    } finally {
      setIsActing(false);
    }
  }

  const ActionIcon = action.icon;

  return (
    <div
      className={cn(
        "border-t border-sidebar-border pt-3",
        collapsed && "text-center",
        className,
      )}
    >
      <p className="px-2 text-xs text-muted-foreground tabular-nums">
        {collapsed ? `v${state.currentVersion}` : `Version ${state.currentVersion}`}
      </p>
      <Button
        type="button"
        size={collapsed ? "icon" : "sm"}
        variant={state.status === "downloaded" ? "default" : "ghost"}
        disabled={disabled}
        aria-busy={
          state.status === "checking" ||
          state.status === "downloading" ||
          state.status === "installing"
        }
        onClick={() => void performAction()}
        title={collapsed ? action.label : undefined}
        className={cn("mt-2", collapsed ? "size-10" : "w-full justify-start")}
      >
        <ActionIcon
          className={cn(
            (state.status === "checking" ||
              state.status === "downloading" ||
              state.status === "installing") &&
              "animate-spin",
          )}
          aria-hidden="true"
        />
        <span className={cn(collapsed && "sr-only")}>{action.label}</span>
      </Button>
      {!collapsed ? (
        <AnimatePresence mode="wait" initial={false}>
          <motion.p
            key={`${state.status}:${state.error ?? ""}`}
            {...appear(reducedMotion)}
            className={cn(
              "mt-1 px-2 text-xs text-muted-foreground",
              state.error && "text-destructive",
            )}
            role="status"
            aria-live="polite"
          >
            {updateStatusLine(state)}
          </motion.p>
        </AnimatePresence>
      ) : null}
    </div>
  );
}

function updateAction(state: UpdateState) {
  if (state.status === "available") {
    return {
      id: "download" as const,
      label: `Download ${state.availableVersion}`,
      icon: Download,
    };
  }
  if (state.status === "downloaded") {
    return { id: "install" as const, label: "Restart to update", icon: RotateCcw };
  }
  if (state.status === "installing") {
    return {
      id: "install" as const,
      label: "Restarting to update",
      icon: RotateCcw,
    };
  }
  if (state.status === "downloading") {
    return {
      id: "download" as const,
      label: `Downloading ${Math.round(state.progress ?? 0)}%`,
      icon: RefreshCw,
    };
  }
  if (state.status === "checking") {
    return { id: "check" as const, label: "Checking for updates", icon: RefreshCw };
  }
  return { id: "check" as const, label: "Check for updates", icon: RefreshCw };
}

function updateStatusLine(state: UpdateState) {
  if (state.error) return state.error;
  if (state.status === "up-to-date") return "Knocklet is up to date.";
  if (state.status === "installing") {
    return "Installing update. Knocklet will restart when ready.";
  }
  if (state.status === "unavailable") return "Updates require the installed app.";
  return "";
}
