import type { Metadata } from "next";
import { Library } from "@/components/Library";

export const metadata: Metadata = { title: "Knowledge Library" };
export default function Page() {
  return <Library />;
}
