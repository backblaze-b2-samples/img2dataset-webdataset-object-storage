"use client";

import Link from "next/link";
import { Database, Layers, Percent } from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import type { Corpus } from "@img2dataset-webdataset-object-storage/shared";
import { CorpusStatusBadge } from "./corpus-status-badge";

export function CorpusCard({ corpus }: { corpus: Corpus }) {
  return (
    <Link href={`/corpora/${corpus.id}`} className="group">
      <Card className="card-hover h-full">
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-2">
            <p className="min-w-0 truncate font-semibold group-hover:text-primary">
              {corpus.name}
            </p>
            <CorpusStatusBadge status={corpus.status} />
          </div>
          {corpus.description && (
            <p className="line-clamp-2 text-xs text-muted-foreground">
              {corpus.description}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            {corpus.output_format} · {corpus.image_size}px · {corpus.resize_mode}
          </p>
          {corpus.status === "complete" && (
            <div className="grid grid-cols-3 gap-2 pt-1">
              <Metric
                icon={Database}
                label="images"
                value={corpus.metrics.successes.toLocaleString()}
              />
              <Metric
                icon={Layers}
                label="shards"
                value={String(corpus.metrics.shard_count)}
              />
              <Metric
                icon={Percent}
                label="yield"
                value={`${corpus.metrics.yield_pct}%`}
              />
            </div>
          )}
          {corpus.status === "complete" && (
            <p className="text-xs text-muted-foreground">
              {corpus.metrics.total_bytes_human} on B2
            </p>
          )}
          {corpus.status === "failed" && corpus.error && (
            <p className="line-clamp-2 text-xs text-destructive">{corpus.error}</p>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Database;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-2 text-center">
      <Icon className="mx-auto h-3.5 w-3.5 text-muted-foreground" aria-hidden />
      <p className="mt-1 text-sm font-semibold tabular-nums">{value}</p>
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
    </div>
  );
}
