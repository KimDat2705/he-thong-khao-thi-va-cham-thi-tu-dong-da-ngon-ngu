import SubmissionDetailView from "./SubmissionDetailView";

// Next.js 16: route params are async and must be awaited.
export default async function SubmissionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <SubmissionDetailView id={id} />;
}
