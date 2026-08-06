"use client";

import { Database, HardDrive, Layers, Percent } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingNotice } from "@/components/common/loading-notice";
import { useCorpusStats } from "@/lib/queries";

export function StatsCards() {
  const { data: stats, isLoading, error, refetch } = useCorpusStats();

  // Surface fetch failures inline rather than rendering zeros — that would lie
  // about the bucket state when really the API is just unreachable.
  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const cards = [
    { title: "Corpora Built", value: stats?.total_corpora ?? 0, icon: Database },
    { title: "Images Ingested", value: (stats?.images_ingested ?? 0).toLocaleString(), icon: Layers },
    {
      title: "Aggregate Yield",
      value: stats ? `${stats.aggregate_yield_pct}%` : "0%",
      icon: Percent,
    },
    { title: "Corpus Bytes on B2", value: stats?.total_bytes_human ?? "0 B", icon: HardDrive },
  ];

  return (
    <>
      {/* Stats scan the img2dataset/ prefix, which can take a moment on a large
          bucket. State that in words rather than showing blank cards. */}
      {isLoading && <LoadingNotice className="mb-3" subject="ingest metrics" />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card, i) => (
          <Card
            key={card.title}
            className={`card-hover animate-fade-in-up stagger-${i + 1}`}
          >
            <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-4 space-y-0">
              <CardTitle className="text-xs font-semibold text-muted-foreground">
                {card.title}
              </CardTitle>
              <div className="stat-icon-wrap">
                <card.icon className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent className="pb-5 px-4">
              {isLoading ? (
                <Skeleton className="h-8 w-24" />
              ) : (
                <div className="stat-value">{card.value}</div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
