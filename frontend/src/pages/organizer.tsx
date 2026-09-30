import { useState } from "react";
import {
  Link,
  NavLink,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowRight,
  Plus,
  ScanLine,
  CheckCircle2,
  MapPin,
  Pencil,
} from "lucide-react";
import { api, allPages } from "../lib/api";
import type { Category, Event, Page, Ticket, Tier, Venue } from "../lib/types";
import { money, when } from "../lib/format";
import { useAuth } from "../auth";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Empty,
  Field,
  Loading,
  Notice,
  Pagination,
  Status,
} from "../components/shared";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "../components/ui/dialog";

export function OrganizerNav() {
  return (
    <nav className="workspace-nav" aria-label="Organizer workspace">
      <NavLink to="/organizer" end>
        My events
      </NavLink>
      <NavLink to="/organizer/venues">My venues</NavLink>
      <NavLink to="/organizer/checkin">Check-in</NavLink>
    </nav>
  );
}
export function OrganizerHome() {
  const [params, setParams] = useSearchParams();
  const query = new URLSearchParams(params);
  query.set("mine", "true");
  const events = useQuery({
    queryKey: ["my-events", query.toString()],
    queryFn: ({ signal }) =>
      api<Page<Event>>(`/api/events/?${query}`, "GET", undefined, signal),
  });
  return (
    <main className="container section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">YOUR ORGANIZER WORKSPACE</span>
          <h1>Make something happen.</h1>
          <p className="muted">
            From the first idea to the last person through the door.
          </p>
        </div>
        <Button asChild>
          <Link to="/organizer/events/new">
            <Plus size={17} />
            Create event
          </Link>
        </Button>
      </div>
      <OrganizerNav />
      <div className="filter-row">
        <span>Events you organize</span>
        <select
          aria-label="Event status"
          value={params.get("status") || ""}
          onChange={(e) =>
            setParams(e.target.value ? { status: e.target.value } : {})
          }
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </div>
      {events.isPending ? (
        <Loading />
      ) : events.isError ? (
        <Notice error={events.error} />
      ) : events.data.results.length ? (
        <>
          <div className="order-list">
            {events.data.results.map((event) => (
              <Link
                className="order-row"
                to={`/organizer/events/${event.id}`}
                key={event.id}
              >
                <div className="order-icon">
                  <Pencil size={20} />
                </div>
                <div>
                  <h3>{event.title}</h3>
                  <p>
                    {when(event.starts_at)} · {event.venue.city}
                  </p>
                </div>
                <Status status={event.status} />
                <ArrowRight className="push-right" size={18} />
              </Link>
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
        <Empty title="Every great event starts somewhere">
          <p>
            Create your first event, add tickets, then publish when you’re
            ready.
          </p>
          <Button asChild>
            <Link to="/organizer/events/new">Create your first event</Link>
          </Button>
        </Empty>
      )}
    </main>
  );
}

const eventSchema = z
  .object({
    title: z.string().min(1, "Give your event a title.").max(200),
    description: z.string(),
    venue_id: z.string().min(1, "Choose a venue."),
    starts_at: z.string().min(1, "Choose a start time."),
    ends_at: z.string().min(1, "Choose an end time."),
    status: z.enum(["draft", "published", "cancelled"]),
    max_tickets_per_user: z.coerce.number().int().min(1).max(32767),
    categories: z.array(z.string()),
  })
  .refine((value) => Date.parse(value.ends_at) > Date.parse(value.starts_at), {
    path: ["ends_at"],
    message: "End time must be after start time.",
  });
type EventFields = z.infer<typeof eventSchema>;
function localTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
    .toISOString()
    .slice(0, 16);
}
export function EventEditor() {
  const { id } = useParams();
  const { user } = useAuth();
  const isNew = !id || id === "new";
  const event = useQuery({
    queryKey: ["event", id],
    queryFn: () => api<Event>(`/api/events/${id}/`),
    enabled: !isNew,
  });
  if (!isNew && event.isPending) return <Loading />;
  if (!isNew && event.isError)
    return (
      <main className="container section">
        <Notice error={event.error} />
      </main>
    );
  if (event.data && event.data.organizer !== user!.id && !user!.is_staff)
    return (
      <main className="container section">
        <Notice>You can only manage events you organize.</Notice>
      </main>
    );
  return (
    <main className="container section">
      <Link className="back-link" to="/organizer">
        ← My events
      </Link>
      <span className="eyebrow">BRING YOUR IDEA TO LIFE</span>
      <h1>{isNew ? "Create an experience." : "Make it your own."}</h1>
      <EventForm key={id || "new"} event={event.data} />
    </main>
  );
}
function EventForm({ event }: { event?: Event }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const venues = useQuery({
    queryKey: ["venues-picker"],
    queryFn: ({ signal }) =>
      allPages<Venue>("/api/venues/?page_size=100", signal),
  });
  const categories = useQuery({
    queryKey: ["categories-picker"],
    queryFn: ({ signal }) =>
      allPages<Category>("/api/categories/?page_size=100", signal),
  });
  const form = useForm<EventFields>({
    resolver: zodResolver(eventSchema),
    defaultValues: {
      title: event?.title || "",
      description: event?.description || "",
      venue_id: event ? String(event.venue.id) : "",
      starts_at: localTime(event?.starts_at),
      ends_at: localTime(event?.ends_at),
      status: event?.status || "draft",
      max_tickets_per_user: event?.max_tickets_per_user || 10,
      categories: event?.categories || [],
    },
  });
  const save = useMutation({
    mutationFn: (values: EventFields) =>
      api<Event>(
        event ? `/api/events/${event.id}/` : "/api/events/",
        event ? "PATCH" : "POST",
        {
          ...values,
          venue_id: Number(values.venue_id),
          starts_at: new Date(values.starts_at).toISOString(),
          ends_at: new Date(values.ends_at).toISOString(),
        },
      ),
    onSuccess: (updated) => {
      void client.invalidateQueries({ queryKey: ["my-events"] });
      void client.invalidateQueries({ queryKey: ["events"] });
      client.setQueryData(["event", String(updated.id)], updated);
      if (!event)
        navigate(`/organizer/events/${updated.id}`, { replace: true });
    },
  });
  return (
    <div className="editor-grid">
      <div>
        <form
          className="panel form-stack"
          onSubmit={form.handleSubmit((values) => save.mutate(values))}
        >
          <h2>The essentials</h2>
          <Field
            label="Event title"
            error={form.formState.errors.title?.message}
          >
            <Input
              placeholder="Give them something to look forward to"
              {...form.register("title")}
            />
          </Field>
          <Field label="Description">
            <textarea
              rows={5}
              placeholder="What makes this event worth showing up for?"
              {...form.register("description")}
            />
          </Field>
          <Field label="Venue" error={form.formState.errors.venue_id?.message}>
            <select {...form.register("venue_id")} disabled={venues.isPending}>
              <option value="">Choose a venue</option>
              {venues.data?.map((venue) => (
                <option key={venue.id} value={venue.id}>
                  {venue.name} · {venue.city}
                </option>
              ))}
            </select>
          </Field>
          <Notice error={venues.error} />
          <Link className="text-link" to="/organizer/venues">
            Manage or add a venue →
          </Link>
          <div className="form-grid">
            <Field
              label="Starts at (your local time)"
              error={form.formState.errors.starts_at?.message}
            >
              <Input type="datetime-local" {...form.register("starts_at")} />
            </Field>
            <Field
              label="Ends at (your local time)"
              error={form.formState.errors.ends_at?.message}
            >
              <Input type="datetime-local" {...form.register("ends_at")} />
            </Field>
          </div>
          <fieldset>
            <legend>Categories</legend>
            <div className="checkbox-row">
              {categories.data?.map((category) => (
                <label key={category.slug}>
                  <input
                    type="checkbox"
                    value={category.slug}
                    {...form.register("categories")}
                  />
                  {category.name}
                </label>
              ))}
            </div>
          </fieldset>
          <Notice error={categories.error} />
          <div className="form-grid">
            <Field label="Status">
              <select {...form.register("status")}>
                <option value="draft">Draft — only you can see it</option>
                <option value="published">
                  Published — visible to everyone
                </option>
                <option value="cancelled" disabled>
                  Cancelled
                </option>
              </select>
            </Field>
            <Field
              label="Ticket limit per person"
              error={form.formState.errors.max_tickets_per_user?.message}
            >
              <Input
                type="number"
                min="1"
                max="32767"
                {...form.register("max_tickets_per_user")}
              />
            </Field>
          </div>
          <Notice error={save.error} />
          {save.isSuccess ? <Notice>Event saved.</Notice> : null}
          <div className="actions">
            <Button
              disabled={
                save.isPending ||
                venues.isPending ||
                venues.isError ||
                categories.isError
              }
            >
              {save.isPending
                ? "Saving…"
                : event
                  ? "Save event"
                  : "Create event"}
            </Button>
            {event ? (
              <Button asChild variant="outline">
                <Link to={`/events/${event.id}`}>
                  View event <ArrowRight size={16} />
                </Link>
              </Button>
            ) : null}
          </div>
        </form>
        {event ? <TierManager event={event} /> : null}
      </div>
      <aside className="editor-note">
        <span className="eyebrow">A GREAT FIRST IMPRESSION</span>
        <h2>
          Small details.
          <br />
          Big difference.
        </h2>
        <p>
          Make the title clear, describe the experience, and double-check the
          place and time.
        </p>
        <ol>
          <li>Save your event as a draft.</li>
          <li>Add ticket tiers and availability.</li>
          <li>Publish when you’re ready.</li>
        </ol>
        <p>Prices are in INR. Demo payments don’t charge your guests.</p>
      </aside>
    </div>
  );
}

function TierManager({ event }: { event: Event }) {
  const [editing, setEditing] = useState<Tier | null | undefined>(undefined);
  const client = useQueryClient();
  return (
    <section className="panel form-stack">
      <div className="section-heading">
        <h2>Ticket tiers</h2>
        <Button variant="outline" onClick={() => setEditing(null)}>
          <Plus size={16} />
          Add tier
        </Button>
      </div>
      {event.ticket_types.map((tier) => (
        <div className="tier-row" key={tier.id}>
          <div>
            <strong>{tier.name}</strong>
            <span>
              {money(tier.price)} · {tier.quantity_available} of{" "}
              {tier.quantity_total} available
            </span>
          </div>
          <Button variant="outline" onClick={() => setEditing(tier)}>
            Edit <span className="sr-only">{tier.name}</span>
          </Button>
        </div>
      ))}
      {!event.ticket_types.length ? (
        <p className="muted">
          Add a ticket tier before inviting people to book.
        </p>
      ) : null}
      <Dialog
        open={editing !== undefined}
        onOpenChange={(open) => {
          if (!open) setEditing(undefined);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editing ? "Edit ticket tier" : "Add ticket tier"}
            </DialogTitle>
            <DialogDescription>
              Changing the total updates available stock while preserving
              existing reservations.
            </DialogDescription>
          </DialogHeader>
          {editing !== undefined ? (
            <TierForm
              key={editing?.id || "new"}
              tier={editing}
              eventId={event.id}
              done={() => {
                setEditing(undefined);
                void client.invalidateQueries({
                  queryKey: ["event", String(event.id)],
                });
                void client.invalidateQueries({ queryKey: ["events"] });
              }}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}
function TierForm({
  tier,
  eventId,
  done,
}: {
  tier: Tier | null;
  eventId: number;
  done: () => void;
}) {
  const save = useMutation({
    mutationFn: (data: FormData) =>
      api(
        tier ? `/api/ticket-types/${tier.id}/` : "/api/ticket-types/",
        tier ? "PATCH" : "POST",
        {
          event: eventId,
          name: data.get("name"),
          price: data.get("price"),
          quantity_total: Number(data.get("quantity_total")),
        },
      ),
    onSuccess: done,
  });
  return (
    <form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(new FormData(e.currentTarget));
      }}
    >
      <Field label="Tier name">
        <Input name="name" required maxLength={100} defaultValue={tier?.name} />
      </Field>
      <Field label="Price (INR)">
        <Input
          name="price"
          type="number"
          min="0"
          step="0.01"
          required
          defaultValue={tier?.price || "0.00"}
        />
      </Field>
      <Field label="Total tickets">
        <Input
          name="quantity_total"
          type="number"
          min="1"
          step="1"
          required
          defaultValue={tier?.quantity_total || 100}
        />
      </Field>
      <Notice error={save.error} />
      <Button disabled={save.isPending}>
        {save.isPending ? "Saving…" : "Save tier"}
      </Button>
    </form>
  );
}

export function VenuesPage() {
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<Venue | null | undefined>(undefined);
  const client = useQueryClient();
  const venues = useQuery({
    queryKey: ["my-venues", page],
    queryFn: () => api<Page<Venue>>(`/api/venues/?mine=true&page=${page}`),
  });
  return (
    <main className="container section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">SET THE SCENE</span>
          <h1>Your venues</h1>
        </div>
        <Button onClick={() => setEditing(null)}>
          <Plus size={18} />
          Add venue
        </Button>
      </div>
      <OrganizerNav />
      {venues.isPending ? (
        <Loading />
      ) : venues.isError ? (
        <Notice error={venues.error} />
      ) : (
        <>
          <div className="event-grid">
            {venues.data.results.map((venue) => (
              <article className="panel venue-card" key={venue.id}>
                <MapPin size={26} />
                <h2>{venue.name}</h2>
                <p>
                  {venue.address}, {venue.city}
                </p>
                <span className="muted">Capacity · {venue.capacity}</span>
                <Button variant="outline" onClick={() => setEditing(venue)}>
                  Edit venue <span className="sr-only">{venue.name}</span>
                </Button>
              </article>
            ))}
          </div>
          {venues.data.count === 0 ? (
            <Empty title="Find a place to bring people together">
              <p>Add your first venue to get started.</p>
            </Empty>
          ) : null}
          <Pagination
            page={page}
            next={venues.data.next}
            previous={venues.data.previous}
            onChange={setPage}
          />
        </>
      )}
      <Dialog
        open={editing !== undefined}
        onOpenChange={(open) => {
          if (!open) setEditing(undefined);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editing ? "Edit venue" : "Add a venue"}</DialogTitle>
            <DialogDescription>
              Give guests a clear location for your event.
            </DialogDescription>
          </DialogHeader>
          {editing !== undefined ? (
            <VenueForm
              key={editing?.id || "new"}
              venue={editing}
              done={() => {
                setEditing(undefined);
                void client.invalidateQueries({ queryKey: ["my-venues"] });
                void client.invalidateQueries({ queryKey: ["venues-picker"] });
              }}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </main>
  );
}
function VenueForm({ venue, done }: { venue: Venue | null; done: () => void }) {
  const save = useMutation({
    mutationFn: (data: FormData) =>
      api(
        venue ? `/api/venues/${venue.id}/` : "/api/venues/",
        venue ? "PATCH" : "POST",
        {
          name: data.get("name"),
          address: data.get("address"),
          city: data.get("city"),
          capacity: Number(data.get("capacity")),
        },
      ),
    onSuccess: done,
  });
  return (
    <form
      className="form-stack"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate(new FormData(e.currentTarget));
      }}
    >
      {(["name", "address", "city"] as const).map((field) => (
        <Field key={field} label={field}>
          <Input name={field} required defaultValue={venue?.[field]} />
        </Field>
      ))}
      <Field label="Capacity">
        <Input
          type="number"
          name="capacity"
          required
          min="1"
          step="1"
          defaultValue={venue?.capacity || 100}
        />
      </Field>
      <Notice error={save.error} />
      <Button disabled={save.isPending}>
        {save.isPending ? "Saving…" : "Save venue"}
      </Button>
    </form>
  );
}

export function CheckinPage() {
  const [code, setCode] = useState("");
  const checkin = useMutation({
    mutationFn: (submittedCode: string) =>
      api<Ticket & { attendee: string }>("/api/checkin/", "POST", {
        code: submittedCode,
      }),
  });
  return (
    <main className="container section">
      <span className="eyebrow">WELCOME THEM IN</span>
      <h1>At the door.</h1>
      <OrganizerNav />
      <div className="narrow panel checkin-panel">
        <ScanLine size={44} />
        <h2>One code. One great experience.</h2>
        <p className="muted">
          Paste or type the guest’s ticket code. You can check in tickets for
          events you organize.
        </p>
        <form
          className="form-stack"
          onSubmit={(e) => {
            e.preventDefault();
            if (!checkin.isPending) checkin.mutate(code.trim());
          }}
        >
          <Field label="Ticket code">
            <Input
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
              required
              maxLength={32}
              disabled={checkin.isPending}
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                checkin.reset();
              }}
              placeholder="Enter the code from their ticket"
            />
          </Field>
          <Button disabled={!code.trim() || checkin.isPending}>
            {checkin.isPending ? "Checking…" : "Check in ticket"}
            <ArrowRight size={17} />
          </Button>
        </form>
        <Notice error={checkin.error} />
        {checkin.data ? (
          <div className="checkin-success" role="status">
            <CheckCircle2 size={32} />
            <h3>You’re all set. Welcome in!</h3>
            <p>{checkin.data.event.title}</p>
            <p>
              {checkin.data.ticket_type.name} · {checkin.data.attendee}
            </p>
            <Button
              variant="outline"
              onClick={() => {
                setCode("");
                checkin.reset();
              }}
            >
              Next guest
            </Button>
          </div>
        ) : null}
      </div>
    </main>
  );
}
