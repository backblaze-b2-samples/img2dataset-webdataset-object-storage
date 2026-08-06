"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Corpus } from "@img2dataset-webdataset-object-storage/shared";

/**
 * Yield validation: numbers read back from the per-shard _stats.json on B2 — the
 * honest measure of how many URLs actually became training images.
 */
export function YieldStats({ corpus }: { corpus: Corpus }) {
  const m = corpus.metrics;
  const rows: [string, string][] = [
    ["Images attempted", m.image_count.toLocaleString()],
    ["Downloaded & packaged", m.successes.toLocaleString()],
    ["Failed", m.failed.toLocaleString()],
    ["Shards written", String(m.shard_count)],
    ["Corpus size on B2", m.total_bytes_human],
    ["Ingest time", `${m.duration_seconds}s`],
  ];

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Yield validation</CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <div className="mb-4 rounded-md border border-border bg-muted/40 p-4">
          <p className="text-xs font-medium text-muted-foreground">
            Download yield
          </p>
          <p className="stat-value">{m.yield_pct}%</p>
          <Progress value={m.yield_pct} className="mt-2 h-2" />
          <p className="mt-2 text-xs text-muted-foreground">
            {m.successes.toLocaleString()} of {m.image_count.toLocaleString()}{" "}
            URLs became images and were streamed to B2. Read straight back from
            each shard&apos;s <code>_stats.json</code>.
          </p>
        </div>
        <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
          {rows.map(([label, value]) => (
            <div
              key={label}
              className="flex items-center justify-between border-b border-border py-1.5"
            >
              <span className="text-sm text-muted-foreground">{label}</span>
              <span className="text-sm font-medium tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
