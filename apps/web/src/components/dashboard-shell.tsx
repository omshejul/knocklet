"use client";

import { Clock3, Send } from "lucide-react";
import { useState } from "react";

import {
  ConnectionImportPanel,
  type DashboardSection,
} from "@/components/connection-import-panel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const sections = [
  { id: "send" as const, label: "Send requests", icon: Send },
  { id: "history" as const, label: "History", icon: Clock3 },
];

export function DashboardShell() {
  const [section, setSection] = useState<DashboardSection>("send");

  return (
    <div className="min-h-screen md:grid md:grid-cols-[14rem_minmax(0,1fr)]">
      <aside className="border-b border-sidebar-border bg-sidebar text-sidebar-foreground md:sticky md:top-0 md:h-screen md:border-r md:border-b-0">
        <div className="mx-auto flex max-w-5xl flex-col items-stretch gap-3 px-4 py-3 md:h-full md:px-3 md:py-5">
          <p className="px-2 text-lg font-bold">LinkedIn</p>

          <nav
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
        </div>
      </aside>

      <main className="min-w-0 px-5 py-8 sm:px-8 md:py-10">
        <div className="mx-auto w-full max-w-5xl">
          <h1 className="text-2xl font-bold tracking-tight">
            {section === "send" ? "Send requests" : "History"}
          </h1>
          <ConnectionImportPanel section={section} />
        </div>
      </main>
    </div>
  );
}
