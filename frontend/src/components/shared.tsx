import type { ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CalendarDays,
  MapPin,
  Ticket,
  Sparkles,
} from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { Event } from "../lib/types";
import { day, money } from "../lib/format";

export function Notice({
  error,
  children,
}: {
  error?: Error | null;
  children?: ReactNode;
}) {
  if (!error && !children) return null;
  return (
    <div
      className={error ? "notice error" : "notice"}
      role={error ? "alert" : "status"}
    >
      {error?.message || children}
    </div>
  );
}
export function Loading() {
  return (
    <div className="container section" role="status" aria-label="Loading">
      <div className="skeleton title-skeleton" />
      <div className="event-grid">
        {[1, 2, 3].map((n) => (
          <div className="skeleton card-skeleton" key={n} />
        ))}
      </div>
      <span className="sr-only">Loading…</span>
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <Ticket size={36} aria-hidden="true" />
      <h2>{title}</h2>
      {children}
    </div>
  );
}
export function Pagination({
  page,
  next,
  previous,
  onChange,
}: {
  page: number;
  next: string | null;
  previous: string | null;
  onChange: (page: number) => void;
}) {
  if (!next && !previous) return null;
  return (
    <nav className="pagination" aria-label="Pagination">
      <Button
        variant="outline"
        disabled={!previous}
        onClick={() => onChange(page - 1)}
      >
        <ArrowLeft size={16} /> Previous
      </Button>
      <span>Page {page}</span>
      <Button
        variant="outline"
        disabled={!next}
        onClick={() => onChange(page + 1)}
      >
        Next <ArrowRight size={16} />
      </Button>
    </nav>
  );
}
export function Status({ status }: { status: string }) {
  return <Badge className={`status status-${status}`}>{status}</Badge>;
}
const palettes: Record<string, string> = {
  music: "coral",
  tech: "blue",
  comedy: "yellow",
  sports: "mint",
  "food-drink": "pink",
};
export function EventArt({
  event,
  large = false,
}: {
  event: Pick<Event, "categories" | "title">;
  large?: boolean;
}) {
  const category = event.categories[0] || "discover";
  return (
    <div
      className={`event-art ${palettes[category] || "lilac"} ${large ? "large" : ""}`}
      aria-hidden="true"
    >
      <div className="art-orbit" />
      <div className="art-disc" />
      <div className="art-bars">
        <i />
        <i />
        <i />
        <i />
        <i />
      </div>
      <span className="art-label">
        {category.replaceAll("-", " ")}
        <Sparkles size={17} />
      </span>
      <span className="art-word">
        {category === "music"
          ? "TURN IT UP."
          : category === "tech"
            ? "WHAT’S NEXT?"
            : category === "comedy"
              ? "GOOD TIMES."
              : category === "sports"
                ? "LET’S GO."
                : "BE THERE."}
      </span>
      <span className="art-footer">A little out of the ordinary. ↗</span>
    </div>
  );
}
export function EventCard({ event }: { event: Event }) {
  const available = event.ticket_types.some(
    (tier) => tier.quantity_available > 0,
  );
  return (
    <Link className="event-card" to={`/events/${event.id}`}>
      <EventArt event={event} />
      <div className="event-card-body">
        <div className="event-meta">
          <span>
            <CalendarDays size={14} />
            {day(event.starts_at)}
          </span>
          {!available ? <span>Sold out</span> : null}
        </div>
        <h3>{event.title}</h3>
        <p>
          <MapPin size={14} />
          {event.venue.name}, {event.venue.city}
        </p>
        <div className="card-bottom">
          <span>
            {event.min_price === null ? (
              "Tickets coming soon"
            ) : Number(event.min_price) === 0 ? (
              "Free entry"
            ) : (
              <>
                <small>From </small>
                {money(event.min_price)}
              </>
            )}
          </span>
          <span className="circle-arrow">
            <ArrowRight size={17} />
          </span>
        </div>
      </div>
    </Link>
  );
}
export function Field({
  label,
  children,
  error,
}: {
  label: string;
  children: ReactNode;
  error?: string;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {error ? (
        <small className="field-error" role="alert">
          {error}
        </small>
      ) : null}
    </label>
  );
}
