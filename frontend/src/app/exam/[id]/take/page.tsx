import TakeView from "../TakeView";

// Next.js 16: route params are async and must be awaited.
export default async function TakePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TakeView id={id} />;
}
