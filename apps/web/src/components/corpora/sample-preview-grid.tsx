"use client";

/* eslint-disable @next/next/no-img-element */
// The thumbnails are tiny base64 data URLs decoded from a WebDataset shard, not
// remote assets — next/image would add no value and cannot optimize a data URL.

import { ImageIcon } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useCorpusPreview } from "@/lib/queries";

/**
 * Stream-back proof: decode the first few (image, caption) pairs from a shard by
 * iterating it with the real WebDataset pipeline — exactly what a training loop
 * does when it streams shards straight from B2.
 */
export function SamplePreviewGrid({
  corpusId,
  enabled,
}: {
  corpusId: string;
  enabled: boolean;
}) {
  const { data, isLoading, error, refetch } = useCorpusPreview(corpusId, enabled);

  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Stream-back preview</CardTitle>
        <CardDescription className="text-xs">
          First samples decoded from a shard via <code>wds.WebDataset(...)</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="p-5">
        {error ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : isLoading ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="aspect-square w-full rounded-md" />
            ))}
          </div>
        ) : !data || data.samples.length === 0 ? (
          <EmptyState
            icon={ImageIcon}
            title="Nothing to stream back yet"
            description={
              data?.note ??
              "Preview needs a completed WebDataset corpus with a non-zero yield."
            }
          />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {data.samples.map((sample) => (
              <figure key={sample.key} className="space-y-1">
                <img
                  src={sample.thumbnail}
                  alt={sample.caption || sample.key}
                  className="aspect-square w-full rounded-md border border-border object-cover"
                />
                <figcaption
                  className="truncate text-xs text-muted-foreground"
                  title={sample.caption}
                >
                  {sample.caption || sample.key}
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
