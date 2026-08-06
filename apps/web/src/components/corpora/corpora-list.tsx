"use client";

import { Database, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useCorpora } from "@/lib/queries";
import { CorpusCard } from "./corpus-card";
import { CorpusFormDialog } from "./corpus-form-dialog";

export function CorporaList() {
  const { data: corpora = [], isLoading, error, refetch } = useCorpora();

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-48 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (corpora.length === 0) {
    return (
      <Card>
        <CardContent className="p-0">
          <EmptyState
            icon={Database}
            title="No corpora yet"
            description="Create a corpus to bulk-download an image-text dataset into B2 as WebDataset shards with img2dataset."
            action={
              <CorpusFormDialog
                mode="create"
                trigger={
                  <Button size="sm">
                    <Plus className="h-3.5 w-3.5" />
                    New corpus
                  </Button>
                }
              />
            }
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {corpora.map((corpus) => (
        <CorpusCard key={corpus.id} corpus={corpus} />
      ))}
    </div>
  );
}
