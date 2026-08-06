import { Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { CorpusStatus } from "@img2dataset-webdataset-object-storage/shared";

const LABELS: Record<CorpusStatus, string> = {
  running: "Ingesting",
  complete: "Complete",
  failed: "Failed",
};

// Complete gets a green tint via a className override (no success variant).
const CLASSNAMES: Record<CorpusStatus, string> = {
  running: "",
  complete: "bg-[var(--brand-b2)] text-white",
  failed: "",
};

const VARIANTS: Record<CorpusStatus, "default" | "secondary" | "destructive"> = {
  running: "default",
  complete: "default",
  failed: "destructive",
};

export function CorpusStatusBadge({ status }: { status: CorpusStatus }) {
  return (
    <Badge variant={VARIANTS[status]} className={CLASSNAMES[status]}>
      {status === "running" && (
        <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
      )}
      {LABELS[status]}
    </Badge>
  );
}
