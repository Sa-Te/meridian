import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { askQuestion, listMeetings } from "@/app/lib/api/client";
import { ApiError } from "@/app/lib/api/client";

import { ChatView } from "./ChatView";

vi.mock("@/app/lib/api/client", async () => {
  const actual = await vi.importActual<typeof import("@/app/lib/api/client")>(
    "@/app/lib/api/client",
  );
  return {
    ...actual,
    askQuestion: vi.fn(),
    listMeetings: vi.fn(),
  };
});

async function askAndSubmit(question: string) {
  fireEvent.change(screen.getByLabelText("Your question"), { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
}

describe("ChatView", () => {
  beforeEach(() => {
    vi.mocked(askQuestion).mockReset();
    vi.mocked(listMeetings).mockResolvedValue([]);
  });

  it("disables the Ask button until a question is entered", () => {
    render(<ChatView />);

    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Your question"), { target: { value: "Hi" } });

    expect(screen.getByRole("button", { name: "Ask" })).toBeEnabled();
  });

  it("shows a loading state, then a supported answer with citations", async () => {
    vi.mocked(askQuestion).mockResolvedValue({
      answer: "Five to seven workouts.",
      supported: true,
      citations: [
        {
          chunk_id: "c1",
          meeting_id: "m1",
          speaker: "Naomi",
          start_ts: 155,
          end_ts: 170,
          text: "At least five to seven logged workouts with heart rate data.",
        },
      ],
    });

    render(<ChatView />);
    await askAndSubmit("How many workouts?");

    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("chat-answer")).toBeInTheDocument();
    });
    expect(screen.getByText("Five to seven workouts.")).toBeInTheDocument();
    expect(screen.getByText("Naomi")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument();
  });

  it("shows a distinct 'not well-supported' panel for a declined answer", async () => {
    vi.mocked(askQuestion).mockResolvedValue({
      answer: "I could not find a well-supported answer to this question in the available transcripts.",
      supported: false,
      citations: [],
    });

    render(<ChatView />);
    await askAndSubmit("What is the capital of France?");

    await waitFor(() => {
      expect(screen.getByTestId("chat-declined")).toBeInTheDocument();
    });
    expect(screen.getByText("Not well-supported")).toBeInTheDocument();
    expect(screen.queryByTestId("chat-answer")).not.toBeInTheDocument();
  });

  it("shows an error panel when the request fails", async () => {
    vi.mocked(askQuestion).mockRejectedValue(new ApiError(500, "Internal Server Error"));

    render(<ChatView />);
    await askAndSubmit("What was decided?");

    await waitFor(() => {
      expect(screen.getByTestId("chat-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Internal Server Error")).toBeInTheDocument();
  });
});
