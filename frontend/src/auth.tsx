import {
  createContext,
  useContext,
  useEffect,
  useState,
  useRef,
  Fragment,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { safeNext } from "./lib/format";
import { api, session, identityChanged } from "./lib/api";
import type { Session, User } from "./lib/types";
import { Notice, Loading } from "./components/shared";

const AuthContext = createContext<{
  user: User | null;
  login: (
    email: string,
    password: string,
    next?: string | null,
  ) => Promise<User>;
  logout: () => Promise<void>;
} | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const navigate = useNavigate();
  const [switching, setSwitching] = useState(false);
  const [transitionError, setTransitionError] = useState<Error | null>(null);
  const channelRef = useRef<BroadcastChannel | null>(null);
  const auth = useQuery({
    queryKey: ["session"],
    queryFn: async () =>
      (await session()).authenticated ? api<User>("/api/auth/me/") : null,
    retry: false,
    staleTime: 60_000,
  });
  useEffect(() => {
    const expire = () => {
      identityChanged();
      void client.cancelQueries();
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
    };
    const channel =
      typeof BroadcastChannel === "undefined"
        ? null
        : new BroadcastChannel("ticket-session");
    channelRef.current = channel;
    if (channel)
      channel.onmessage = async () => {
        identityChanged();
        setSwitching(true);
        await client.cancelQueries();
        client.removeQueries({
          predicate: (query) => query.queryKey[0] !== "session",
        });
        try {
          await client.invalidateQueries({ queryKey: ["session"] });
        } finally {
          setSwitching(false);
        }
      };
    window.addEventListener("session-expired", expire);
    return () => {
      window.removeEventListener("session-expired", expire);
      channel?.close();
      channelRef.current = null;
    };
  }, [client]);
  const publish = () => {
    // Reuse the listener's channel so the sending tab does not notify itself.
    channelRef.current?.postMessage("changed");
  };
  async function login(email: string, password: string, next?: string | null) {
    setTransitionError(null);
    setSwitching(true);
    identityChanged();
    await client.cancelQueries();
    try {
      await api<Session>("/api/auth/session/", "POST", { email, password });
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
      publish();
      const user = await api<User>("/api/auth/me/");
      client.setQueryData(["session"], user);
      navigate(
        next ? safeNext(next) : user.role === "organizer" ? "/organizer" : "/",
        { replace: true },
      );
      return user;
    } catch (error) {
      setTransitionError(error as Error);
      // The server may have changed the cookie even if the response was lost.
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
      publish();
      await client.invalidateQueries({ queryKey: ["session"] });
      throw error;
    } finally {
      setSwitching(false);
    }
  }
  async function logout() {
    setTransitionError(null);
    setSwitching(true);
    identityChanged();
    await client.cancelQueries();
    try {
      await api("/api/auth/session/", "DELETE");
      navigate("/", { replace: true });
    } catch (error) {
      setTransitionError(error as Error);
      throw error;
    } finally {
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
      publish();
      await client.invalidateQueries({ queryKey: ["session"] });
      setSwitching(false);
    }
  }
  if (auth.isPending || switching) return <Loading />;
  if (auth.isError)
    return (
      <main className="container section">
        <Notice error={auth.error} />
        <button className="text-link" onClick={() => void auth.refetch()}>
          Reconnect
        </button>
      </main>
    );
  return (
    <AuthContext.Provider value={{ user: auth.data ?? null, login, logout }}>
      {transitionError ? (
        <div className="container">
          <Notice error={transitionError} />
        </div>
      ) : null}
      <Fragment key={auth.data?.id ?? "guest"}>{children}</Fragment>
    </AuthContext.Provider>
  );
}
// The provider and its hook intentionally share this module.
// oxlint-disable-next-line react/only-export-components
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("AuthProvider required");
  return context;
}
export function Protected({
  children,
  organizer = false,
}: {
  children: ReactNode;
  organizer?: boolean;
}) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user)
    return (
      <Navigate
        to={`/login?next=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  if (organizer && user.role !== "organizer" && !user.is_staff)
    return (
      <main className="container section">
        <h1>Organizer access required</h1>
        <p>Sign in with an organizer account to manage events.</p>
      </main>
    );
  return children;
}
