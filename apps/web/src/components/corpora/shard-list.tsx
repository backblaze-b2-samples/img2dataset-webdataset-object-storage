"use client";

import { Layers } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { EmptyState } from "@/components/ui/empty-state";
import type { ShardStat } from "@img2dataset-webdataset-object-storage/shared";

export function ShardList({ shards }: { shards: ShardStat[] }) {
  return (
    <Card>
      <CardHeader className="border-b border-border py-4 px-5">
        <CardTitle className="card-title">Shards on B2</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {shards.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No shards"
            description="This corpus produced no shards. A zero-yield run writes stats but no packaged images."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Shard
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Success / Attempted
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Failed DL
                </TableHead>
                <TableHead className="text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Size
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {shards.map((shard) => (
                <TableRow key={shard.name} className="table-row-hover">
                  <TableCell className="font-mono text-xs">
                    {shard.tar_key ? `${shard.name}.tar` : shard.name}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {shard.successes} / {shard.count}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {shard.failed_to_download}
                  </TableCell>
                  <TableCell className="text-right tabular-nums text-muted-foreground">
                    {shard.size_human}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
