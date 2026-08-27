"use client";

import { motion, useReducedMotion } from "framer-motion";
import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { appear } from "@/lib/motion";

function LoadingState({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.p
      {...appear(reducedMotion)}
      className={cn(
        "flex items-center gap-2 text-sm text-muted-foreground",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      <span>{children}</span>
    </motion.p>
  );
}

export { LoadingState };
