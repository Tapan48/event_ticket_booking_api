import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Link,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Search,
  MapPin,
  CalendarDays,
  Ticket,
  ShieldCheck,
  Clock3,
  SlidersHorizontal,
} from "lucide-react";
import { api } from "../lib/api";
import type { Category, Event, Order, Page } from "../lib/types";
import { money, when, localDayStart } from "../lib/format";
import { useAuth } from "../auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  EventArt,
  EventCard,
  Empty,
  Field,
  Loading,
  Notice,
  Pagination,
  Status,
} from "../components/shared";

export function Catalog() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams(params);
  query.set("upcoming", "true");
  query.set("status", "published");
  query.set("page_size", "9");
  const localDate = params.get("from_date");
  query.delete("from_date");
  const startsAfter = localDayStart(localDate);
  if (startsAfter) query.set("starts_after", startsAfter);
  const events = useQuery({
    queryKey: ["events", query.toString()],
    queryFn: ({ signal }) =>
      api<Page<Event>>(`/api/events/?${query}`, "GET", undefined, signal),
  });
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: () => api<Page<Category>>("/api/categories/?page_size=100"),
  });
  const update = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    next.delete("page");
    setParams(next);
  };
  const category = params.get("category") || "";
  return (
    <>
      <section className="hero container">
        <div className="hero-copy">
          <span className="eyebrow">
            <span className="green-dot" /> LESS SCROLLING. MORE LIVING.
          </span>
          <h1>
            Good plans.
            <br />
            Great <span>memories.</span>
          </h1>
          <p>
            Live music, fresh ideas, and something a little unexpected. Find
            your next “glad I went.”
          </p>
          <a className="hero-cta" href="#discover">
            Find your next event <ArrowUpRight size={20} />
          </a>
          <div className="hero-foot">
            <span className="mini-avatars">
              <i>A</i>
              <i>M</i>
              <i>R</i>
            </span>
            <span>
              For the curious. For the together.
              <br />
              <strong>For you.</strong>
            </span>
          </div>
        </div>
        <div className="hero-art" aria-hidden="true">
          <div className="hero-sun" />
          <span className="hero-spark">✳</span>
          <div className="hero-ticket ticket-back">
            <span>YOUR NEXT CHAPTER</span>
            <strong>
              GO
              <br />
              ALL IN.
            </strong>
            <div className="ticket-perf" />
            <span>MAKE A MEMORY ↗</span>
          </div>
          <div className="hero-ticket ticket-front">
            <span>ADMIT ONE · GOOD TIMES</span>
            <Ticket size={44} />
            <strong>
              Be there.
              <br />
              Feel it all.
            </strong>
            <div className="ticket-perf" />
            <span>THE BEST PLANS START HERE</span>
          </div>
          <span className="hero-sticker">
            OUT OF
            <br />
            OFFICE ↗
          </span>
        </div>
      </section>
      <section id="discover" className="container section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">YOUR NEXT GOOD STORY</span>
            <h2>What’s happening?</h2>
          </div>
          <span className="muted">A little something for everyone.</span>
        </div>
        <form
          className="search-bar"
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            const next = new URLSearchParams(params);
            for (const name of ["search", "city"]) {
              const value = String(data.get(name) || "").trim();
              if (value) next.set(name, value);
              else next.delete(name);
            }
            next.delete("page");
            setParams(next);
          }}
          key={`${params.get("search")}-${params.get("city")}`}
        >
          <label>
            <Search size={20} />
            <input
              aria-label="Search events"
              name="search"
              defaultValue={params.get("search") || ""}
              placeholder="Artists, events, or a new experience…"
            />
          </label>
          <label className="city-search">
            <MapPin size={19} />
            <input
              aria-label="City"
              name="city"
              defaultValue={params.get("city") || ""}
              placeholder="Any city"
            />
          </label>
          <Button type="submit">
            Find events <ArrowRight size={17} />
          </Button>
        </form>
        <div className="category-row">
          <button
            className={!category ? "chip selected" : "chip"}
            onClick={() => update("category", "")}
          >
            ✳ All experiences
          </button>
          {categories.data?.results.map((item) => (
            <button
              key={item.slug}
              className={category === item.slug ? "chip selected" : "chip"}
              onClick={() => update("category", item.slug)}
            >
              {item.name}
            </button>
          ))}
        </div>
        <div className="filter-row">
          <span className="result-count">
            {events.data
              ? `${events.data.count} upcoming experiences`
              : "Finding experiences…"}
          </span>
          <details className="more-filters">
            <summary>
              <SlidersHorizontal size={15} /> Filters
            </summary>
            <div className="filter-fields">
              <Field label="From date">
                <input
                  type="date"
                  value={params.get("from_date") || ""}
                  onChange={(e) => update("from_date", e.target.value)}
                />
              </Field>
              <Field label="Min price (INR)">
                <input
                  type="number"
                  min="0"
                  value={params.get("min_price") || ""}
                  onChange={(e) => update("min_price", e.target.value)}
                />
              </Field>
              <Field label="Max price (INR)">
                <input
                  type="number"
                  min="0"
                  value={params.get("max_price") || ""}
                  onChange={(e) => update("max_price", e.target.value)}
                />
              </Field>
              <button className="text-link" onClick={() => setParams({})}>
                Reset filters
              </button>
            </div>
          </details>
          <select
            aria-label="Sort events"
            value={params.get("ordering") || "starts_at"}
            onChange={(e) => update("ordering", e.target.value)}
          >
            <option value="starts_at">Soonest first</option>
            <option value="min_price">Price: low to high</option>
            <option value="-min_price">Price: high to low</option>
          </select>
        </div>
        {events.isPending ? (
          <Loading />
        ) : events.isError ? (
          <>
            <Notice error={events.error} />
            <Button variant="outline" onClick={() => void events.refetch()}>
              Try again
            </Button>
          </>
        ) : events.data.results.length ? (
          <>
            <div className="event-grid">
              {events.data.results.map((event) => (
                <EventCard key={event.id} event={event} />
              ))}
            </div>
            <Pagination
              page={Number(params.get("page") || 1)}
              next={events.data.next}
              previous={events.data.previous}
              onChange={(page) => {
                const next = new URLSearchParams(params);
                next.set("page", String(page));
                setParams(next);
              }}
            />
          </>
        ) : (
          <Empty title="No plans here just yet">
            <p>Try another city, category, or date.</p>
            <Button onClick={() => setParams({})}>Clear filters</Button>
          </Empty>
        )}
      </section>
      <section className="container organizer-banner">
        <div>
          <span className="eyebrow">BRING PEOPLE TOGETHER</span>
          <h2>Your idea. Their next great night.</h2>
          <p>Create an event, open the doors, and let the memories happen.</p>
        </div>
        <Button asChild>
          <Link to="/organizer">
            Create an event <ArrowUpRight size={18} />
          </Link>
        </Button>
      </section>
    </>
  );
}

export function EventDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const event = useQuery({
    queryKey: ["event", id],
    queryFn: ({ signal }) =>
      api<Event>(`/api/events/${id}/`, "GET", undefined, signal),
  });
  const [selection, setSelection] = useState<{
    eventId: string | undefined;
    values: Record<number, number>;
  }>({ eventId: id, values: {} });
  const quantities: Record<number, number> = Object.fromEntries(
    (event.data?.ticket_types || []).map((tier) => [
      tier.id,
      selection.eventId === id
        ? Math.min(
            selection.values[tier.id] || 0,
            tier.quantity_available,
            event.data!.max_tickets_per_user,
            100,
          )
        : 0,
    ]),
  );
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const booking = useMutation({
    mutationFn: () =>
      api<Order>("/api/orders/", "POST", {
        event: Number(id),
        items: Object.entries(quantities)
          .filter(([, quantity]) => quantity > 0)
          .map(([ticket_type, quantity]) => ({
            ticket_type: Number(ticket_type),
            quantity,
          })),
      }),
    onSuccess: (order) => {
      void client.invalidateQueries({ queryKey: ["events"] });
      navigate(`/orders/${order.id}`);
    },
    onError: () => {
      void event.refetch();
    },
  });
  if (event.isPending) return <Loading />;
  if (event.isError)
    return (
      <main className="container section">
        <Notice error={event.error} />
        <Link className="text-link" to="/">
          Back to events
        </Link>
      </main>
    );
  const data = event.data;
  const count = Object.values(quantities).reduce((sum, n) => sum + n, 0);
  const total =
    data.ticket_types.reduce(
      (sum, tier) =>
        sum + Math.round(Number(tier.price) * 100) * (quantities[tier.id] || 0),
      0,
    ) / 100;
  const bookable =
    data.status === "published" && Date.parse(data.starts_at) > now;
  return (
    <main className="container section">
      <Link to="/#discover" className="back-link">
        ← Explore events
      </Link>
      <div className="detail-grid">
        <article>
          <EventArt event={data} large />
          <div className="detail-heading">
            <Status status={data.status} />
            <h1>{data.title}</h1>
            <p>
              <CalendarDays size={18} />
              {when(data.starts_at)}
            </p>
            <p>
              <MapPin size={18} />
              {data.venue.name}, {data.venue.city}
            </p>
          </div>
          <section className="prose">
            <h2>About this experience</h2>
            <p>
              {data.description ||
                "Something worth showing up for. Choose your ticket and join us."}
            </p>
            <p>
              Ends {when(data.ends_at)}. Times are shown in your local time
              zone.
            </p>
          </section>
        </article>
        <aside className="booking-panel">
          <span className="eyebrow">SAVE YOUR SPOT</span>
          <h2>Make it a plan.</h2>
          <p className="muted">Choose your tickets. Good times await.</p>
          {data.ticket_types.map((tier) => (
            <div className="tier-row" key={tier.id}>
              <div>
                <strong>{tier.name}</strong>
                <span>
                  {Number(tier.price) === 0 ? "Free" : money(tier.price)}
                </span>
                <small>
                  {tier.quantity_available > 0
                    ? `${tier.quantity_available} available`
                    : "Sold out"}
                </small>
              </div>
              <Input
                aria-label={`${tier.name} quantity`}
                type="number"
                min="0"
                max={Math.min(
                  tier.quantity_available,
                  data.max_tickets_per_user,
                  100,
                )}
                disabled={!bookable || tier.quantity_available === 0}
                value={quantities[tier.id] || 0}
                onChange={(e) =>
                  setSelection({
                    eventId: id,
                    values: {
                      ...quantities,
                      [tier.id]: Math.max(
                        0,
                        Math.min(
                          Math.floor(Number(e.target.value)),
                          tier.quantity_available,
                          data.max_tickets_per_user,
                          100,
                        ),
                      ),
                    },
                  })
                }
              />
            </div>
          ))}
          {!data.ticket_types.length ? (
            <Notice>Tickets haven’t been released yet.</Notice>
          ) : null}
          <div className="total-row">
            <span>
              Total · {count} ticket{count === 1 ? "" : "s"}
            </span>
            <strong>{money(total)}</strong>
          </div>
          <Notice error={booking.error} />
          {booking.isError ? (
            <Link to="/orders" className="text-link">
              Check my orders before retrying
            </Link>
          ) : null}
          {!bookable ? (
            <Notice>This event is not accepting bookings.</Notice>
          ) : user ? (
            <Button
              className="wide"
              disabled={
                count < 1 ||
                count > data.max_tickets_per_user ||
                booking.isPending
              }
              onClick={() => booking.mutate()}
            >
              {booking.isPending ? "Reserving…" : "Reserve tickets"}
              <ArrowRight size={17} />
            </Button>
          ) : (
            <Button className="wide" asChild>
              <Link to={`/login?next=/events/${id}`}>
                Sign in to book <ArrowRight size={17} />
              </Link>
            </Button>
          )}
          <p className="helper">
            <Clock3 size={15} /> Reserved for 15 minutes while you pay.
          </p>
          <p className="helper">
            <ShieldCheck size={15} /> Demo checkout. No real money charged.
          </p>
          <small className="muted">
            Maximum {data.max_tickets_per_user} tickets per person, including
            existing reservations.
          </small>
        </aside>
      </div>
    </main>
  );
}
