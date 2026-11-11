import type { Metadata } from "next";
import { Suspense } from "react";
import { DocumentViewer } from "@/components/DocumentViewer";
import { Skeleton } from "@/components/ui";

export const metadata: Metadata = { title: "Document" };

// With Cache Components, runtime params must be read inside a Suspense boundary.
async function Viewer({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DocumentViewer id={id} />;
}

export default function Page({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<div className="p-6"><Skeleton className="h-96" /></div>}>
      <Viewer params={params} />
    </Suspense>
  );
}
