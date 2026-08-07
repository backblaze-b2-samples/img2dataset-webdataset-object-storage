import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CorpusFormDialog } from "@/components/corpora/corpus-form-dialog";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { RecentCorporaTable } from "@/components/dashboard/recent-corpora-table";
import { CorporaChart } from "@/components/dashboard/corpora-chart";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            img2dataset ingest into Backblaze B2 at a glance — corpora built,
            images packaged into WebDataset shards, download yield, and bytes on B2.
          </p>
        </div>
        {/* Same dialog the /corpora page opens — the dashboard's primary CTA
            goes straight to the create form (and, on submit, to the new
            corpus's detail page) instead of hopping through the list page. */}
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
      <StatsCards />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="animate-fade-in-up stagger-3">
          <CorporaChart />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <RecentCorporaTable />
        </div>
      </div>
    </div>
  );
}
