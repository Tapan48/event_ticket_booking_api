import { lazy, Suspense, useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { ArrowUpRight, Ticket } from "lucide-react";
import { AuthProvider, Protected, useAuth } from "./auth";
import { ApiError } from "./lib/api";
import { Button } from "./components/ui/button";
import { Loading, Notice } from "./components/shared";
import { Catalog, EventDetail } from "./pages/catalog";
import "./App.css";

const AuthPage = lazy(() =>
  import("./pages/account").then((m) => ({ default: m.AuthPage })),
);
const ProfilePage = lazy(() =>
  import("./pages/account").then((m) => ({ default: m.ProfilePage })),
);
const OrdersPage = lazy(() =>
  import("./pages/orders").then((m) => ({ default: m.OrdersPage })),
);
const OrderDetail = lazy(() =>
  import("./pages/orders").then((m) => ({ default: m.OrderDetail })),
);
const OrganizerHome = lazy(() =>
  import("./pages/organizer").then((m) => ({ default: m.OrganizerHome })),
);
const EventEditor = lazy(() =>
  import("./pages/organizer").then((m) => ({ default: m.EventEditor })),
);
const VenuesPage = lazy(() =>
  import("./pages/organizer").then((m) => ({ default: m.VenuesPage })),
);
const CheckinPage = lazy(() =>
  import("./pages/organizer").then((m) => ({ default: m.CheckinPage })),
);
const client = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: (count, error) =>
        count < 1 && (!(error instanceof ApiError) || error.status >= 500),
    },
    mutations: { retry: false },
  },
});

function Shell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [logoutError, setLogoutError] = useState<Error | null>(null);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (!location.hash) window.scrollTo(0, 0);
    document.title = "Be There — Event Ticket Booking";
  }, [location.pathname, location.hash]);
  async function signOut() {
    setLeaving(true);
    setLogoutError(null);
    try {
      await logout();
      navigate("/");
    } catch (error) {
      setLogoutError(error as Error);
    } finally {
      setLeaving(false);
    }
  }
  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container header-inner">
          <Link className="brand" to="/" aria-label="Be There home">
            <span className="brand-icon">
              <Ticket size={25} />
            </span>
            be there<span className="brand-dot">.</span>
          </Link>
          <nav className="main-nav" aria-label="Main navigation">
            <NavLink to="/" end>
              Discover
            </NavLink>
            {user ? (
              <>
                <NavLink to="/tickets">My tickets</NavLink>
                <NavLink to="/orders">Orders</NavLink>
                {user.role === "organizer" || user.is_staff ? (
                  <NavLink to="/organizer">Organize</NavLink>
                ) : null}
              </>
            ) : (
              <NavLink to="/register">
                For organizers <ArrowUpRight size={13} />
              </NavLink>
            )}
          </nav>
          <div className="header-actions">
            {user ? (
              <>
                <Link className="account-link" to="/profile">
                  {user.first_name || "My account"}
                </Link>
                <Button
                  variant="outline"
                  disabled={leaving}
                  onClick={() => void signOut()}
                >
                  Sign out
                </Button>
              </>
            ) : (
              <>
                <Link className="sign-in-link" to="/login">
                  Sign in
                </Link>
                <Button asChild>
                  <Link to="/register">
                    Get started <ArrowUpRight size={16} />
                  </Link>
                </Button>
              </>
            )}
          </div>
        </div>
      </header>
      {logoutError ? (
        <div className="container">
          <Notice error={logoutError} />
        </div>
      ) : null}
      <div id="main" className="page-body">
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route path="/" element={<Catalog />} />
            <Route path="/events/:id" element={<EventDetail />} />
            <Route path="/login" element={<AuthPage key="login" />} />
            <Route
              path="/register"
              element={<AuthPage key="register" register />}
            />
            <Route
              path="/profile"
              element={
                <Protected>
                  <ProfilePage />
                </Protected>
              }
            />
            <Route
              path="/orders"
              element={
                <Protected>
                  <OrdersPage />
                </Protected>
              }
            />
            <Route
              path="/orders/:id"
              element={
                <Protected>
                  <OrderDetail />
                </Protected>
              }
            />
            <Route
              path="/tickets"
              element={
                <Protected>
                  <OrdersPage tickets />
                </Protected>
              }
            />
            <Route
              path="/organizer"
              element={
                <Protected organizer>
                  <OrganizerHome />
                </Protected>
              }
            />
            <Route
              path="/organizer/events/:id"
              element={
                <Protected organizer>
                  <EventEditor />
                </Protected>
              }
            />
            <Route
              path="/organizer/venues"
              element={
                <Protected organizer>
                  <VenuesPage />
                </Protected>
              }
            />
            <Route
              path="/organizer/checkin"
              element={
                <Protected organizer>
                  <CheckinPage />
                </Protected>
              }
            />
            <Route
              path="*"
              element={
                <main className="container section narrow">
                  <h1>This one’s off the map.</h1>
                  <p>
                    That page doesn’t exist. There are plenty of good plans back
                    home.
                  </p>
                  <Button asChild>
                    <Link to="/">Discover events</Link>
                  </Button>
                </main>
              }
            />
          </Routes>
        </Suspense>
      </div>
      <footer className="site-footer">
        <div className="container footer-inner">
          <div>
            <Link className="brand" to="/">
              be there<span className="brand-dot">.</span>
            </Link>
            <p>Less ordinary. More unforgettable.</p>
          </div>
          <div>
            <span>Event Ticket Booking · Portfolio demo</span>
            <p>Mock payments. Real good plans.</p>
            <a href="/api/docs/">Developer API / Swagger ↗</a>
          </div>
        </div>
      </footer>
    </>
  );
}
export default function App() {
  return (
    <QueryClientProvider client={client}>
      <BrowserRouter>
        <AuthProvider>
          <Shell />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
