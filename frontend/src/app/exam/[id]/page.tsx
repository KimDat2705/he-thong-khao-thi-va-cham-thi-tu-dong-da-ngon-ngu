import ExamView from "./ExamView";

// Next.js 16: route params are async and must be awaited.
export default async function ExamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ExamView id={id} />;
}
