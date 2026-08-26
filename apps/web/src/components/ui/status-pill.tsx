import {
  CheckCircle2,
  Circle,
  CircleAlert,
  CircleMinus,
  CircleX,
  Clock3,
  LoaderCircle,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Tone = "active" | "danger" | "neutral" | "success" | "warning";

const statusStyles: Record<
  string,
  { icon: LucideIcon; tone: Tone; spinning?: boolean }
> = {
  accepted: { icon: CheckCircle2, tone: "success" },
  already_connected: { icon: CheckCircle2, tone: "success" },
  complete: { icon: CheckCircle2, tone: "success" },
  connected: { icon: CheckCircle2, tone: "success" },
  sent: { icon: CheckCircle2, tone: "success" },
  succeeded: { icon: CheckCircle2, tone: "success" },
  checking: { icon: LoaderCircle, tone: "active", spinning: true },
  running: { icon: LoaderCircle, tone: "active", spinning: true },
  sending: { icon: LoaderCircle, tone: "active", spinning: true },
  queued: { icon: Clock3, tone: "active" },
  ready: { icon: Circle, tone: "active" },
  pending: { icon: Clock3, tone: "warning" },
  needs_review: { icon: CircleAlert, tone: "warning" },
  failed: { icon: CircleX, tone: "danger" },
  invalid: { icon: CircleX, tone: "danger" },
  cancelled: { icon: CircleMinus, tone: "neutral" },
  duplicate: { icon: CircleMinus, tone: "neutral" },
  not_scheduled: { icon: CircleMinus, tone: "neutral" },
  not_started: { icon: CircleMinus, tone: "neutral" },
  skipped: { icon: CircleMinus, tone: "neutral" },
};

const toneClasses: Record<Tone, string> = {
  active: "border-info/30 bg-info/10 text-info",
  danger: "border-destructive/30 bg-destructive/10 text-destructive",
  neutral: "border-border bg-muted/40 text-muted-foreground",
  success: "border-success/30 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-warning",
};

export function StatusPill({ status }: { status: string }) {
  const style = statusStyles[status] ?? {
    icon: Circle,
    tone: "neutral" as const,
  };
  const Icon = style.icon;

  return (
    <Badge variant="outline" className={toneClasses[style.tone]}>
      <Icon
        data-icon="inline-start"
        aria-hidden="true"
        className={cn(style.spinning && "animate-spin")}
      />
      {status.replaceAll("_", " ")}
    </Badge>
  );
}
