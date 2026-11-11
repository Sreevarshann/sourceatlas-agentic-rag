import type { Metadata } from "next";
import { Suspense } from "react";
import { Studio } from "@/components/Studio";
import { Skeleton } from "@/components/ui";

export const metadata: Metadata = { title: "Research Studio" };
export default function Page() {
  return (
    <Suspense fallback={<div className="p-6"><Skeleton className="h-64" /></div>}>
      <Studio />
    </Suspense>
  );
}
