"use client";

import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useCorpusProgress } from "@/lib/queries";

/**
 * Live progress for an ingest that is still running.
 *
 * A bulk ingest scales with the URL list, so a bare spinner tells a user
 * nothing for the whole run. Every number here is polled back from B2 (shards
 * whose `_stats.json` has landed, versus the shards still pending in
 * img2dataset's `_tmp` folder) — nothing is timer-driven, so a stalled run
 * visibly stops advancing instead of animating on.
 */
export function CorpusIngestProgress({ corpusId }: { corpusId: string }) {
  const { data } = useCorpusProgress(corpusId, true);

  const percent = data?.percent ?? null;
  const shardsTotal = data?.shards_total ?? null;

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" aria-hidden />
          Ingest in progress
        </CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <div
          role="status"
          aria-live="polite"
          className="flex items-baseline justify-between gap-3"
        >
          <p className="text-sm font-medium">
            {data?.stage ?? "Starting the ingest"}
          </p>
          <p className="text-sm font-semibold tabular-nums">
            {percent === null ? "—" : `${Math.round(percent)}%`}
          </p>
        </div>

        {percent === null ? (
          // Total not known yet (img2dataset hasn't planned the shards): an
          // indeterminate track, never a fake percentage.
          <div className="progress-indeterminate mt-2 h-2 w-full rounded-full" />
        ) : (
          <Progress value={percent} className="mt-2 h-2" />
        )}

        <dl className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2 sm:grid-cols-3">
          <Stat
            label="Shards written"
            value={
              shardsTotal === null
                ? String(data?.shards_completed ?? 0)
                : `${data?.shards_completed ?? 0} of ${shardsTotal}`
            }
          />
          <Stat
            label="Images ingested"
            value={(data?.images_written ?? 0).toLocaleString()}
          />
          <Stat label="Elapsed" value={formatElapsed(data?.elapsed_seconds ?? 0)} />
        </dl>

        <p className="mt-4 text-xs text-muted-foreground">
          Counts are read back from the shards img2dataset has already streamed
          to B2, so they only move when real data lands.
        </p>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border py-1.5">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{value}</dd>
    </div>
  );
}

/** Seconds -> "42s" / "3m 05s". Exported for tests. */
export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  return `${minutes}m ${String(total % 60).padStart(2, "0")}s`;
}
