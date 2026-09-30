import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, it } from "vitest";
import { EventCard, Notice } from "./shared";
import type { Event } from "../lib/types";
it("presents real availability and a navigable event card", () => {
  const event = {
    id: 7,
    title: "A real event",
    categories: ["music"],
    starts_at: "2027-10-12T18:00:00Z",
    venue: { name: "Hall", city: "Pune" },
    min_price: "50.00",
    ticket_types: [{ quantity_available: 0 }],
  } as Event;
  render(
    <MemoryRouter>
      <EventCard event={event} />
    </MemoryRouter>,
  );
  expect(screen.getByText("Sold out")).toBeInTheDocument();
  expect(screen.getByRole("link")).toHaveAttribute("href", "/events/7");
});
it("announces errors accessibly", () => {
  render(<Notice error={new Error("Reservation expired.")} />);
  expect(screen.getByRole("alert")).toHaveTextContent("Reservation expired.");
});
