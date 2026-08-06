import Link from "next/link";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
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
        <Button asChild size="sm" className="h-8">
          <Link href="/corpora">
            <Plus className="h-3.5 w-3.5" />
            New corpus
          </Link>
        </Button>
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
