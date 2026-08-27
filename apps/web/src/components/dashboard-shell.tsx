"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Logs,
  Menu,
  MessageSquareText,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Settings,
  Users,
} from "lucide-react";
import { useState } from "react";

import { ConnectionImportPanel } from "@/components/connection-import-panel";
import { LogsPanel } from "@/components/logs-panel";
import { MessagesPanel } from "@/components/messages-panel";
import { PeoplePanel } from "@/components/people-panel";
import { SettingsPanel } from "@/components/settings-panel";
import { UpdateNav } from "@/components/update-nav";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { appear } from "@/lib/motion";

const sections = [
  { id: "send" as const, label: "Send requests", icon: Send },
  { id: "people" as const, label: "People", icon: Users },
  { id: "messages" as const, label: "Messages", icon: MessageSquareText },
  { id: "logs" as const, label: "Logs", icon: Logs },
  { id: "settings" as const, label: "Settings", icon: Settings },
];

type DashboardSection = (typeof sections)[number]["id"];

export function DashboardShell() {
  const reducedMotion = useReducedMotion();
  const [section, setSection] = useState<DashboardSection>("send");
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const sectionLabel = sections.find((item) => item.id === section)?.label;

  return (
    <div
      className={cn(
        "min-h-screen md:grid",
        isCollapsed
          ? "md:grid-cols-[4.5rem_minmax(0,1fr)]"
          : "md:grid-cols-[14rem_minmax(0,1fr)]",
      )}
    >
      <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-sidebar-border bg-sidebar/95 px-4 text-sidebar-foreground backdrop-blur md:hidden">
        <p className="text-lg font-normal">Knocklet</p>
        <Button
          type="button"
          variant="outline"
          size="icon"
          onClick={() => setIsMobileNavOpen(true)}
          aria-label="Open navigation"
          aria-expanded={isMobileNavOpen}
          className="size-11"
        >
          <Menu aria-hidden="true" />
        </Button>
        <Sheet open={isMobileNavOpen} onOpenChange={setIsMobileNavOpen}>
          <SheetContent side="left">
            <SheetHeader>
              <SheetTitle>Knocklet</SheetTitle>
            </SheetHeader>
            <nav aria-label="Dashboard" className="flex flex-col gap-1 px-3">
              {sections.map((item) => {
                const Icon = item.icon;
                const isActive = section === item.id;
                return (
                  <Button
                    key={item.id}
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setSection(item.id);
                      setIsMobileNavOpen(false);
                    }}
                    aria-current={isActive ? "page" : undefined}
                    className={cn(
                      "min-h-11 justify-start px-3 text-muted-foreground",
                      isActive &&
                        "bg-sidebar-accent text-sidebar-accent-foreground",
                    )}
                  >
                    <Icon aria-hidden="true" />
                    {item.label}
                  </Button>
                );
              })}
            </nav>
            <UpdateNav className="mt-auto mx-3 mb-3" />
          </SheetContent>
        </Sheet>
      </header>

      <aside className="hidden border-sidebar-border bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:block md:h-screen md:border-r">
        <div className="mx-auto flex max-w-5xl flex-col items-stretch gap-3 px-4 py-3 md:h-full md:px-3 md:py-5">
          <div
            className={cn(
              "flex items-center",
              isCollapsed ? "md:justify-center" : "md:justify-between",
            )}
          >
            <p
              className={cn(
                "px-2 text-lg font-normal",
                isCollapsed && "md:hidden",
              )}
            >
              Knocklet
            </p>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              onClick={() => setIsCollapsed((current) => !current)}
              aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!isCollapsed}
              aria-controls="dashboard-navigation"
              title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden size-11 md:inline-flex"
            >
              {isCollapsed ? (
                <PanelLeftOpen aria-hidden="true" />
              ) : (
                <PanelLeftClose aria-hidden="true" />
              )}
            </Button>
          </div>

          <nav
            id="dashboard-navigation"
            aria-label="Dashboard"
            className="grid grid-cols-3 gap-1 md:mt-2 md:flex md:flex-col"
          >
            {sections.map((item) => {
              const Icon = item.icon;
              const isActive = section === item.id;
              return (
                <Button
                  key={item.id}
                  type="button"
                  variant="ghost"
                  onClick={() => setSection(item.id)}
                  aria-current={isActive ? "page" : undefined}
                  title={isCollapsed ? item.label : undefined}
                  className={cn(
                    "min-h-11 justify-start px-3 text-muted-foreground",
                    isCollapsed && "md:justify-center md:px-0",
                    isActive &&
                      "bg-sidebar-accent text-sidebar-accent-foreground",
                  )}
                >
                  <Icon aria-hidden="true" />
                  <span className={cn(isCollapsed && "md:sr-only")}>
                    {item.label}
                  </span>
                </Button>
              );
            })}
          </nav>
          <UpdateNav collapsed={isCollapsed} className="mt-auto" />
        </div>
      </aside>

      <main className="min-w-0 px-4 py-6 sm:px-8 md:py-10">
        <div className="mx-auto w-full max-w-5xl">
          <AnimatePresence mode="popLayout" initial={false}>
            <motion.div key={section} {...appear(reducedMotion)}>
              {section !== "messages" ? (
                <h1 className="text-2xl font-normal tracking-tight">
                  {sectionLabel}
                </h1>
              ) : null}
              {section === "send" ? (
                <ConnectionImportPanel section="send" />
              ) : section === "people" ? (
                <PeoplePanel />
              ) : section === "messages" ? (
                <MessagesPanel />
              ) : section === "logs" ? (
                <LogsPanel />
              ) : (
                <SettingsPanel />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}
