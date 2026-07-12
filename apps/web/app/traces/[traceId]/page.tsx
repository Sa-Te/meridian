import { TraceDetailView } from "@/app/components/traces/TraceDetailView";

interface TraceDetailPageProps {
  params: Promise<{ traceId: string }>;
}

export default async function TraceDetailPage({ params }: TraceDetailPageProps) {
  const { traceId } = await params;
  return <TraceDetailView traceId={traceId} />;
}
