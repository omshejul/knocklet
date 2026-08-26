"use client";

import { PanelLeftClose, PanelLeftOpen, Send, Users } from "lucide-react";
import { useState } from "react";

import { ConnectionImportPanel } from "@/components/connection-import-panel";
import { PeoplePanel } from "@/components/people-panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const sections = [
  { id: "send" as const, label: "Send requests", icon: Send },
  { id: "people" as const, label: "People", icon: Users },
];

type DashboardSection = (typeof sections)[number]["id"];

export function DashboardShell() {
  const [section, setSection] = useState<DashboardSection>("send");
  const [isCollapsed, setIsCollapsed] = useState(false);

  return (
    <div
      className={cn(
        "min-h-screen md:grid",
        isCollapsed
          ? "md:grid-cols-[4.5rem_minmax(0,1fr)]"
          : "md:grid-cols-[14rem_minmax(0,1fr)]",
      )}
    >
      <aside className="border-b border-sidebar-border bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:h-screen md:border-r md:border-b-0">
        <div className="mx-auto flex max-w-5xl flex-col items-stretch gap-3 px-4 py-3 md:h-full md:px-3 md:py-5">
          <div
            className={cn(
              "flex items-center",
              isCollapsed ? "md:justify-center" : "md:justify-between",
            )}
          >
            <p
              className={cn(
                "px-2 text-lg font-bold",
                isCollapsed && "md:hidden",
              )}
            >
              LinkedIn
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
            className="grid grid-cols-2 gap-1 md:mt-2 md:flex md:flex-col"
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
        </div>
      </aside>

      <main className="min-w-0 px-5 py-8 sm:px-8 md:py-10">
        <div className="mx-auto w-full max-w-5xl">
          <h1 className="text-2xl font-bold tracking-tight">
            {section === "send" ? "Send requests" : "People"}
          </h1>
          {section === "send" ? (
            <ConnectionImportPanel section="send" />
          ) : (
            <PeoplePanel />
          )}
        </div>
      </main>
    </div>
  );
}
