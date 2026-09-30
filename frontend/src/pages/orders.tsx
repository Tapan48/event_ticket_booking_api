import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  Clock3,
  Mail,
  Ticket as TicketIcon,
} from "lucide-react";
import { api } from "../lib/api";
import type { Order, Page, Ticket } from "../lib/types";
import { minutesLeft, money, when } from "../lib/format";
import { useAuth } from "../auth";
import { Button } from "../components/ui/button";
import {
  Empty,
  Loading,
  Notice,
  Pagination,
  Status,
} from "../components/shared";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogClose,
} from "../components/ui/dialog";

export function Countdown({ expires }: { expires: string }) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="countdown">
      <Clock3 size={18} /> {minutesLeft(expires, now)} remaining
    </span>
  );
}
export function OrdersPage({ tickets = false }: { tickets?: boolean }) {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") || 1);
  const query = tickets
    ? `/api/tickets/?page=${page}`
    : `/api/orders/?${params}`;
  const orders = useQuery({
    queryKey: [tickets ? "tickets" : "orders", user!.id, query],
    queryFn: ({ signal }) =>
      api<Page<Order & Ticket>>(query, "GET", undefined, signal),
    refetchInterval: tickets ? false : 15_000,
  });
  const change = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    if (name !== "page") next.delete("page");
    setParams(next);
  };
  return (
    <main className="container section">
      <div className="section-heading">
        <div>
          <span className="eyebrow">GOOD TIMES, ALL IN ONE PLACE</span>
          <h1>{tickets ? "Your tickets" : "Your orders"}</h1>
          <p className="muted">
            {tickets
              ? "Your entry to the experiences you’re looking forward to."
              : "Pick up a reservation or revisit a great plan."}
          </p>
        </div>
        <Button asChild variant="outline">
          <Link to="/">
            Explore events <ArrowRight size={17} />
          </Link>
        </Button>
      </div>
      {!tickets ? (
        <div className="category-row">
          {["", "pending", "paid", "cancelled", "expired"].map((status) => (
            <button
              key={status}
              className={
                (params.get("status") || "") === status
                  ? "chip selected"
                  : "chip"
              }
              onClick={() => change("status", status)}
            >
              {status || "All orders"}
            </button>
          ))}
        </div>
      ) : null}
      {orders.isPending ? (
        <Loading />
      ) : orders.isError ? (
        <Notice error={orders.error} />
      ) : orders.data.results.length ? (
        <>
          <div className={tickets ? "ticket-grid" : "order-list"}>
            {orders.data.results.map((item) =>
              tickets ? (
                <article className="ticket-card" key={item.id}>
                  <div className="ticket-top">
                    <TicketIcon size={25} />
                    <Status
                      status={item.checked_in_at ? "checked-in" : "paid"}
                    />
                  </div>
                  <h2>{item.event?.title}</h2>
                  <p>{item.event && when(item.event.starts_at)}</p>
                  <span className="muted">
                    {item.ticket_type.name} · {money(item.price_paid)}
                  </span>
                  <div className="ticket-code">
                    <small>YOUR ENTRY CODE</small>
                    <code>{item.code}</code>
                    <span>
                      Show this code at the door. It can be checked in once.
                    </span>
                  </div>
                  <Link className="text-link" to={`/orders/${item.order}`}>
                    View order →
                  </Link>
                </article>
              ) : (
                <Link
                  className="order-row"
                  key={item.id}
                  to={`/orders/${item.id}`}
                >
                  <div className="order-icon">
                    <TicketIcon />
                  </div>
                  <div>
                    <small className="muted">
                      ORDER #{item.id} · {when(item.created_at)}
                    </small>
                    <h3>{item.event?.title || "Event unavailable"}</h3>
                    <p>
                      {item.tickets.length} ticket
                      {item.tickets.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="order-row-end">
                    <Status status={item.status} />
                    <strong>{money(item.total_amount)}</strong>
                  </div>
                  <ArrowRight size={18} />
                </Link>
              ),
            )}
          </div>
          <Pagination
            page={page}
            next={orders.data.next}
            previous={orders.data.previous}
            onChange={(n) => change("page", String(n))}
          />
        </>
      ) : (
        <Empty
          title={tickets ? "Your next memory is waiting" : "No orders here yet"}
        >
          <p>
            {tickets
              ? "Your paid tickets will appear here."
              : "Discover an event and reserve your spot."}
          </p>
          <Button asChild>
            <Link to="/">Find an event</Link>
          </Button>
        </Empty>
      )}
    </main>
  );
}

export function OrderDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const client = useQueryClient();
  const [cancelOpen, setCancelOpen] = useState(false);
  const [now, setNow] = useState(Date.now);
  const order = useQuery({
    queryKey: ["order", user!.id, id],
    queryFn: ({ signal }) =>
      api<Order>(`/api/orders/${id}/`, "GET", undefined, signal),
    refetchInterval: (query) =>
      query.state.data?.status === "pending" ? 5000 : false,
  });
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const action = useMutation({
    mutationFn: (verb: "pay" | "cancel") =>
      api<Order>(`/api/orders/${id}/${verb}/`, "POST"),
    onSuccess: (updated) => {
      client.setQueryData(["order", user!.id, id], updated);
      void client.invalidateQueries({ queryKey: ["orders"] });
      void client.invalidateQueries({ queryKey: ["tickets"] });
      void client.invalidateQueries({ queryKey: ["events"] });
      setCancelOpen(false);
    },
    onError: () => {
      void order.refetch();
    },
  });
  if (order.isPending) return <Loading />;
  if (order.isError)
    return (
      <main className="container section">
        <Notice error={order.error} />
        <Link to="/orders" className="text-link">
          Back to orders
        </Link>
      </main>
    );
  const data = order.data;
  const overdue = Date.parse(data.expires_at) <= now;
  return (
    <main className="container section narrow">
      <Link className="back-link" to="/orders">
        ← Your orders
      </Link>
      <div className="order-detail-heading">
        {data.status === "paid" ? (
          <CheckCircle2 size={44} />
        ) : (
          <TicketIcon size={44} />
        )}
        <span className="eyebrow">ORDER #{data.id}</span>
        <h1>
          {data.status === "paid"
            ? "You’re going!"
            : data.status === "pending" && !overdue
              ? "Your spot is on hold."
              : "Your reservation has ended."}
        </h1>
        <Status status={data.status} />
      </div>
      <article className="panel">
        <h2>{data.event?.title}</h2>
        <p className="muted">{data.event && when(data.event.starts_at)}</p>
        {data.tickets.map((ticket) => (
          <div className="order-ticket" key={ticket.id}>
            <div>
              <strong>{ticket.ticket_type.name}</strong>
              <span>{money(ticket.price_paid)}</span>
            </div>
            {ticket.code ? (
              <div>
                <code>{ticket.code}</code>
                <small>
                  {ticket.checked_in_at
                    ? `Checked in ${when(ticket.checked_in_at)}`
                    : "Show this code at the door"}
                </small>
              </div>
            ) : null}
          </div>
        ))}
        <div className="total-row">
          <span>Total</span>
          <strong>{money(data.total_amount)}</strong>
        </div>
      </article>
      <Notice error={action.error} />
      {action.isError ? (
        <Button variant="outline" onClick={() => void order.refetch()}>
          Refresh order status
        </Button>
      ) : null}
      {data.status === "pending" ? (
        <div className="panel checkout-panel">
          <Countdown expires={data.expires_at} />
          {overdue ? (
            <Notice>
              The payment window has closed. Your tickets will be released
              automatically.
            </Notice>
          ) : (
            <>
              <h2>One last step.</h2>
              <p>This is a demo payment. No card details or real charge.</p>
              <Button
                className="wide"
                disabled={action.isPending || overdue}
                onClick={() => action.mutate("pay")}
              >
                {action.isPending ? "Processing…" : "Complete demo payment"}
                <ArrowRight size={18} />
              </Button>
              <p className="helper">
                <Mail size={16} /> Ticket email goes to {user!.email} after
                payment.
              </p>
            </>
          )}
          <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
            <DialogTrigger asChild>
              <Button variant="ghost" disabled={action.isPending}>
                Cancel reservation
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Release these tickets?</DialogTitle>
                <DialogDescription>
                  Your reservation will be cancelled and its tickets made
                  available again.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">Keep reservation</Button>
                </DialogClose>
                <Button
                  disabled={action.isPending}
                  onClick={() => action.mutate("cancel")}
                >
                  Confirm cancellation
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      ) : data.status === "paid" ? (
        <>
          <Notice>
            Ticket email has been queued for {user!.email}. You can also use the
            codes above or find them in My tickets.
          </Notice>
          <Button asChild className="wide">
            <Link to="/tickets">
              View my tickets <ArrowRight size={18} />
            </Link>
          </Button>
        </>
      ) : (
        <Button asChild className="wide">
          <Link to="/">
            Find another experience <ArrowRight size={18} />
          </Link>
        </Button>
      )}
    </main>
  );
}
