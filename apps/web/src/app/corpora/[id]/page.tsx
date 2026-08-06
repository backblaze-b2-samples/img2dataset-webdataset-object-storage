import { CorpusDetail } from "@/components/corpora/corpus-detail";

export default async function CorpusDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="animate-fade-in">
      <CorpusDetail id={id} />
    </div>
  );
}
