import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CorporaList } from "@/components/corpora/corpora-list";
import { CorpusFormDialog } from "@/components/corpora/corpus-form-dialog";

export default function CorporaPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div className="min-w-0">
          <h1 className="page-title">Corpora</h1>
          <p className="mt-1.5 max-w-prose text-sm text-muted-foreground">
            img2dataset ingest jobs. Each corpus bulk-downloads an image-text
            dataset and streams WebDataset <code>.tar</code> shards straight to
            Backblaze B2 under the <code>img2dataset/</code> prefix — a scoped,
            sample-specific view of the bucket.
          </p>
        </div>
        <CorpusFormDialog
          mode="create"
          trigger={
            <Button size="sm" className="h-8 shrink-0">
              <Plus aria-hidden="true" className="h-3.5 w-3.5" />
              New corpus
            </Button>
          }
        />
      </div>
      <div className="animate-fade-in-up stagger-2">
        <CorporaList />
      </div>
    </div>
  );
}
