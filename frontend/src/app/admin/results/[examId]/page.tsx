import ResultsView from "./ResultsView";

// Next.js 16: route params are async and must be awaited.
export default async function ResultsPage({
  params,
}: {
  params: Promise<{ examId: string }>;
}) {
  const { examId } = await params;
  return <ResultsView examId={examId} />;
}
