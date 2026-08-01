import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DatePicker } from "./DatePicker";

describe("DatePicker", () => {
  it("caps the selectable date at maxDate", () => {
    render(<DatePicker maxDate="2026-01-04" value="" onChange={() => {}} />);

    expect(screen.getByLabelText(/fecha/i)).toHaveAttribute("max", "2026-01-04");
  });

  it("calls onChange with the selected date", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();
    render(<DatePicker maxDate="2026-01-04" value="" onChange={handleChange} />);

    await user.type(screen.getByLabelText(/fecha/i), "2026-01-03");

    expect(handleChange).toHaveBeenCalledWith("2026-01-03");
  });
});
