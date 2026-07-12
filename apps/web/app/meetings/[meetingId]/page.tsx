import { MeetingDetailView } from "@/app/components/meetings/MeetingDetailView";

interface MeetingDetailPageProps {
  params: Promise<{ meetingId: string }>;
}

export default async function MeetingDetailPage({ params }: MeetingDetailPageProps) {
  const { meetingId } = await params;
  return <MeetingDetailView meetingId={meetingId} />;
}
