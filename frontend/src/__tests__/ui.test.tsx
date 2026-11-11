import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Chip, Empty } from "@/components/ui";

describe("ui primitives", () => {
  it("renders empty state with action", () => {
    render(<Empty icon={<span>i</span>} title="Nothing here" action={<button>Go</button>}>hint</Empty>);
    expect(screen.getByRole("heading", { name: "Nothing here" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Go" })).toBeInTheDocument();
  });
  it("renders chips", () => {
    render(<Chip tone="teal">indexed</Chip>);
    expect(screen.getByText("indexed")).toBeInTheDocument();
  });
});
