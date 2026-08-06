"use client";

import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Pencil, Play, RotateCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { useCorpus, useDeleteCorpus, useReingestCorpus } from "@/lib/queries";
import { CorpusFormDialog } from "./corpus-form-dialog";
import { CorpusStatusBadge } from "./corpus-status-badge";
import { ShardList } from "./shard-list";
import { SamplePreviewGrid } from "./sample-preview-grid";
import { YieldStats } from "./yield-stats";

export function CorpusDetail({ id }: { id: string }) {
  const router = useRouter();
  const { data: corpus, isLoading, error, refetch } = useCorpus(id);
  const reingest = useReingestCorpus();
  const deleteCorpus = useDeleteCorpus();

  if (error) return <ErrorState error={error} onRetry={() => refetch()} />;
  if (isLoading || !corpus) return <Skeleton className="h-96 w-full rounded-md" />;

  const busy = corpus.status === "running" || reingest.isPending;

  const onReingest = async () => {
    try {
      await reingest.mutateAsync(corpus.id);
      toast.success("Re-ingest started");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Could not start the re-ingest");
    }
  };

  const onDelete = async () => {
    try {
      await deleteCorpus.mutateAsync(corpus.id);
      toast.success("Corpus deleted");
      router.push("/corpora");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border pb-5">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="page-title truncate">{corpus.name}</h1>
            <CorpusStatusBadge status={corpus.status} />
          </div>
          <p className="mt-1.5 text-sm text-muted-foreground">
            {corpus.output_format} · {corpus.image_size}px · updated{" "}
            {new Date(corpus.updated_at).toLocaleString()}
          </p>
          {corpus.description && (
            <p className="mt-1 max-w-prose text-sm text-muted-foreground">
              {corpus.description}
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onReingest} disabled={busy} size="sm">
            {corpus.status === "running" ? (
              <Play className="h-3.5 w-3.5" />
            ) : (
              <RotateCw className="h-3.5 w-3.5" />
            )}
            Re-run ingest
          </Button>
          <CorpusFormDialog
            mode="edit"
            corpus={corpus}
            trigger={
              <Button size="sm" variant="outline" disabled={busy}>
                <Pencil className="h-3.5 w-3.5" />
                Edit
              </Button>
            }
          />
          <ConfirmDialog
            title="Delete this corpus?"
            description={`This deletes the manifest and every shard, parquet, and stats file under ${corpus.prefix} on B2. Scoped to this corpus only. This cannot be undone.`}
            onConfirm={onDelete}
            trigger={
              <Button size="sm" variant="outline" className="text-destructive">
                <Trash2 className="h-3.5 w-3.5" />
                Delete
              </Button>
            }
          />
        </div>
      </div>

      {corpus.status === "failed" && corpus.error && (
        <Alert variant="destructive">
          <AlertTitle>Ingest failed</AlertTitle>
          <AlertDescription>{corpus.error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader className="border-b border-border py-4 px-5">
          <CardTitle className="card-title">Configuration</CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <ConfigRow
            label="URL list"
            value={
              corpus.url_list_source === "seed"
                ? "Built-in seed list (24 images)"
                : (corpus.bucket_key ?? "Uploaded file")
            }
          />
          <ConfigRow label="Output format" value={corpus.output_format} />
          <ConfigRow label="Resize mode" value={corpus.resize_mode} />
          <ConfigRow label="Image size" value={`${corpus.image_size}px`} />
          <ConfigRow label="B2 prefix" value={corpus.prefix} mono />
        </CardContent>
      </Card>

      {corpus.status === "complete" && (
        <>
          <YieldStats corpus={corpus} />
          <SamplePreviewGrid corpusId={corpus.id} enabled={corpus.status === "complete"} />
          <ShardList shards={corpus.shards} />
        </>
      )}
    </div>
  );
}

function ConfigRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border py-2 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={`truncate text-sm font-medium ${mono ? "font-mono text-xs" : ""}`}>
        {value}
      </span>
    </div>
  );
}
