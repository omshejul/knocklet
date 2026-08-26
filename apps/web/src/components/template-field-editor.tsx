"use client";

import { useMemo, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export type TemplateField = {
  name: string;
  label: string;
  placeholder: string;
};

type ActiveTrigger = {
  start: number;
  cursor: number;
  query: string;
};

type TemplateFieldEditorProps = {
  id: string;
  value: string;
  fields: TemplateField[];
  disabled?: boolean;
  onChange: (value: string) => void;
};

const fieldTokenPattern = /\{[^{}]*\}|[{}]/g;

export function TemplateFieldEditor({
  id,
  value,
  fields,
  disabled = false,
  onChange,
}: TemplateFieldEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const highlighterRef = useRef<HTMLDivElement>(null);
  const [activeTrigger, setActiveTrigger] = useState<ActiveTrigger | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const validFields = useMemo(
    () => new Set(fields.map((field) => field.placeholder)),
    [fields],
  );
  const filteredFields = activeTrigger
    ? fields.filter((field) =>
        `${field.label} ${field.name}`
          .toLowerCase()
          .includes(activeTrigger.query.toLowerCase()),
      )
    : [];
  const error = getTemplateFieldError(value, fields);
  const segments = splitTemplate(value, validFields);
  const menuOpen = activeTrigger !== null && filteredFields.length > 0;

  function updateActiveTrigger(textarea: HTMLTextAreaElement) {
    setActiveTrigger(findActiveTrigger(textarea.value, textarea.selectionStart));
    setSelectedIndex(0);
  }

  function insertField(field: TemplateField) {
    if (!activeTrigger) return;
    const nextValue =
      value.slice(0, activeTrigger.start) +
      field.placeholder +
      value.slice(activeTrigger.cursor);
    const nextCursor = activeTrigger.start + field.placeholder.length;
    onChange(nextValue);
    setActiveTrigger(null);
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(nextCursor, nextCursor);
    });
  }

  return (
    <div className="relative mt-2">
      <div className="relative">
        <div
          ref={highlighterRef}
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words rounded-xl border border-transparent px-3 py-3 text-base leading-6 text-foreground"
        >
          {segments.map((segment, index) =>
            segment.kind === "field" ? (
              <span
                key={`${segment.text}-${index}`}
                className="rounded bg-primary/15 text-primary ring-1 ring-inset ring-primary/30"
              >
                {segment.text}
              </span>
            ) : segment.kind === "invalid" ? (
              <span
                key={`${segment.text}-${index}`}
                className="rounded bg-destructive/15 text-destructive underline decoration-wavy underline-offset-2"
              >
                {segment.text}
              </span>
            ) : (
              <span key={`${segment.text}-${index}`}>{segment.text}</span>
            ),
          )}
        </div>
        <textarea
          ref={textareaRef}
          id={id}
          value={value}
          onChange={(event) => {
            onChange(event.currentTarget.value);
            updateActiveTrigger(event.currentTarget);
          }}
          onClick={(event) => updateActiveTrigger(event.currentTarget)}
          onKeyUp={(event) => {
            if (
              ["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
            ) {
              updateActiveTrigger(event.currentTarget);
            }
          }}
          onKeyDown={(event) => {
            if (!menuOpen) return;
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setSelectedIndex((current) =>
                (current + 1) % filteredFields.length,
              );
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setSelectedIndex((current) =>
                (current - 1 + filteredFields.length) % filteredFields.length,
              );
            } else if (event.key === "Enter" || event.key === "Tab") {
              event.preventDefault();
              insertField(filteredFields[selectedIndex] ?? filteredFields[0]);
            } else if (event.key === "Escape") {
              event.preventDefault();
              setActiveTrigger(null);
            }
          }}
          onScroll={(event) => {
            if (!highlighterRef.current) return;
            highlighterRef.current.scrollTop = event.currentTarget.scrollTop;
            highlighterRef.current.scrollLeft = event.currentTarget.scrollLeft;
          }}
          disabled={disabled}
          rows={6}
          placeholder="Thanks for connecting, {first_name}."
          role="combobox"
          aria-expanded={menuOpen}
          aria-controls={`${id}-fields`}
          aria-autocomplete="list"
          aria-haspopup="listbox"
          aria-activedescendant={
            menuOpen
              ? `${id}-field-${filteredFields[selectedIndex]?.name}`
              : undefined
          }
          aria-invalid={Boolean(error)}
          className="relative block min-h-40 w-full resize-y overflow-auto rounded-xl border border-input bg-transparent px-3 py-3 text-base leading-6 text-transparent caret-foreground outline-none selection:bg-primary/30 focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
        />
      </div>

      {menuOpen ? (
        <div
          id={`${id}-fields`}
          role="listbox"
          aria-label="Message fields"
          className="absolute left-3 top-[calc(100%-0.5rem)] z-20 min-w-52 overflow-hidden rounded-lg border bg-popover p-1 text-popover-foreground shadow-md"
        >
          {filteredFields.map((field, index) => (
            <button
              key={field.name}
              id={`${id}-field-${field.name}`}
              type="button"
              role="option"
              aria-selected={index === selectedIndex}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => insertField(field)}
              className={cn(
                "flex min-h-10 w-full items-center justify-between gap-4 rounded-md px-2.5 py-2 text-left text-sm outline-none",
                index === selectedIndex && "bg-accent text-accent-foreground",
              )}
            >
              <span>{field.label}</span>
              <span className="text-xs text-muted-foreground">
                {field.placeholder}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function getTemplateFieldError(
  value: string,
  fields: TemplateField[],
) {
  const validFields = new Set(fields.map((field) => field.placeholder));
  const tokens = value.match(fieldTokenPattern) ?? [];
  const invalid = tokens.find((token) => !validFields.has(token));
  if (!invalid) return "";
  if (invalid === "{") return "Choose a field from the menu.";
  return `Unknown field ${invalid}. Choose a field from the menu.`;
}

function splitTemplate(value: string, validFields: Set<string>) {
  const segments: { text: string; kind: "text" | "field" | "invalid" }[] = [];
  let lastIndex = 0;
  for (const match of value.matchAll(fieldTokenPattern)) {
    const index = match.index;
    if (index > lastIndex) {
      segments.push({ text: value.slice(lastIndex, index), kind: "text" });
    }
    segments.push({
      text: match[0],
      kind: validFields.has(match[0]) ? "field" : "invalid",
    });
    lastIndex = index + match[0].length;
  }
  if (lastIndex < value.length) {
    segments.push({ text: value.slice(lastIndex), kind: "text" });
  }
  return segments;
}

function findActiveTrigger(value: string, cursor: number): ActiveTrigger | null {
  const start = value.lastIndexOf("{", Math.max(0, cursor - 1));
  if (start < 0 || cursor <= start) return null;
  const lastClose = value.lastIndexOf("}", Math.max(0, cursor - 1));
  if (lastClose > start) return null;
  const query = value.slice(start + 1, cursor);
  if (!/^[a-z_]*$/.test(query)) return null;
  return { start, cursor, query };
}
