export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  role: "attendee" | "organizer";
  is_staff: boolean;
  profile: { phone: string; bio: string; city: string };
}
export interface Venue {
  id: number;
  name: string;
  address: string;
  city: string;
  capacity: number;
  created_by: number | null;
}
export interface Category {
  name: string;
  slug: string;
}
export interface Tier {
  id: number;
  event: number;
  name: string;
  price: string;
  quantity_total: number;
  quantity_available: number;
}
export interface Event {
  id: number;
  title: string;
  description: string;
  organizer: number;
  venue: Pick<Venue, "id" | "name" | "city">;
  categories: string[];
  starts_at: string;
  ends_at: string;
  status: "draft" | "published" | "cancelled";
  max_tickets_per_user: number;
  min_price: string | null;
  ticket_types: Tier[];
}
export interface Ticket {
  id: number;
  code: string | null;
  ticket_type: Pick<Tier, "id" | "name">;
  price_paid: string;
  checked_in_at: string | null;
  order: number;
  event: Pick<Event, "id" | "title" | "starts_at">;
}
export interface Order {
  id: number;
  status: "pending" | "paid" | "cancelled" | "expired";
  total_amount: string;
  expires_at: string;
  paid_at: string | null;
  created_at: string;
  event: Pick<Event, "id" | "title" | "starts_at"> | null;
  tickets: Ticket[];
}
export interface Session {
  csrf_token: string;
  authenticated: boolean;
}
