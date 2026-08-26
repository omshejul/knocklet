"use client";

import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useRef,
} from "react";

type RangeSelectionId = string | number;

function isRangeSelectionEvent(event: Event) {
  return "shiftKey" in event && Boolean(event.shiftKey);
}

function useRangeSelection<Id extends RangeSelectionId>(
  orderedIds: readonly Id[],
  setSelectedIds: Dispatch<SetStateAction<Set<Id>>>,
) {
  const anchorRef = useRef<Id | null>(null);

  const resetRangeAnchor = useCallback(() => {
    anchorRef.current = null;
  }, []);

  const toggleRangeSelection = useCallback(
    (id: Id, checked: boolean, event: Event) => {
      const anchor = anchorRef.current;
      let targetIds = [id];

      if (anchor !== null && isRangeSelectionEvent(event)) {
        const anchorIndex = orderedIds.indexOf(anchor);
        const currentIndex = orderedIds.indexOf(id);
        if (anchorIndex >= 0 && currentIndex >= 0) {
          targetIds = orderedIds.slice(
            Math.min(anchorIndex, currentIndex),
            Math.max(anchorIndex, currentIndex) + 1,
          );
        }
      }

      setSelectedIds((current) => {
        const next = new Set(current);
        for (const targetId of targetIds) {
          if (checked) next.add(targetId);
          else next.delete(targetId);
        }
        return next;
      });
      anchorRef.current = id;
    },
    [orderedIds, setSelectedIds],
  );

  return { resetRangeAnchor, toggleRangeSelection };
}

export { useRangeSelection };
