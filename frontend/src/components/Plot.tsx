"use client";

import dynamic from "next/dynamic";
import type { Data, Layout } from "plotly.js";
import { useTheme } from "./theme";
import { Skeleton } from "./ui";

const Plotly = dynamic(
  async () => {
    const [{ default: factory }, plotly] = await Promise.all([import("react-plotly.js/factory"), import("plotly.js-dist-min")]);
    return factory(plotly.default ?? plotly);
  },
  { ssr: false, loading: () => <Skeleton className="h-72 w-full" /> },
);

export function Plot({ data, layout, height = 320, label }: { data: Data[]; layout?: Partial<Layout>; height?: number; label: string }) {
  const { theme } = useTheme();
  const ink = theme === "dark" ? "#efeaf8" : "#1e1d3a";
  const grid = theme === "dark" ? "#34324d" : "#e2d9c8";
  return (
    <div role="img" aria-label={label}>
      <Plotly
        data={data}
        useResizeHandler
        style={{ width: "100%", height }}
        config={{ displaylogo: false, responsive: true }}
        layout={{ autosize: true, height, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: { color: ink, size: 12 }, colorway: theme === "dark" ? ["#a7a4ff", "#5fd1c6", "#e0c48d", "#f08a84"] : ["#2f2c7a", "#237d78", "#c9a96e", "#b4413c"], margin: { l: 48, r: 16, t: 16, b: 48 }, legend: { orientation: "h", y: -0.25 }, xaxis: { gridcolor: grid }, yaxis: { gridcolor: grid }, ...layout }}
      />
    </div>
  );
}
