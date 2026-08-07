import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { CorpusStatus } from "@img2dataset-webdataset-object-storage/shared";

const LABELS: Record<CorpusStatus, string> = {
  running: "Ingesting",
  complete: "Complete",
  failed: "Failed",
};

/**
 * Terminal states must be tellable apart at a glance, not by reading the label.
 * Success used to render in the brand red, which is a hair away from the
 * destructive red the failed badge uses — a corpora list of red pills where
 * only the word differs. Now: blue = in flight, green = succeeded, red =
 * failed, each backed by an existing design token (`--primary`, `--success`,
 * `--destructive`) so both themes stay in sync with the palette.
 *
 * Colour is additive, never the only cue: every badge keeps its text label and
 * carries a distinct icon (spinner / check / cross) for anyone who can't
 * separate the hues.
 */
export const STATUS_CLASSNAMES: Record<CorpusStatus, string> = {
  running: "border-primary/30 bg-accent-subtle text-primary",
  complete: "border-success/30 bg-success-subtle text-success",
  failed: "", // the destructive variant's own filled red — the only red left
};

export const STATUS_VARIANTS: Record<CorpusStatus, "outline" | "destructive"> = {
  running: "outline",
  complete: "outline",
  failed: "destructive",
};

const ICONS: Record<CorpusStatus, LucideIcon> = {
  running: Loader2,
  complete: CheckCircle2,
  failed: XCircle,
};

export function CorpusStatusBadge({ status }: { status: CorpusStatus }) {
  const Icon = ICONS[status];
  return (
    <Badge variant={STATUS_VARIANTS[status]} className={STATUS_CLASSNAMES[status]}>
      <Icon
        className={`h-3 w-3 ${status === "running" ? "animate-spin" : ""}`}
        aria-hidden
      />
      {LABELS[status]}
    </Badge>
  );
}
