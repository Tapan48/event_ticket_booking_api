import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Ticket } from "lucide-react";
import { useAuth } from "../auth";
import { api } from "../lib/api";
import { safeNext } from "../lib/format";
import type { User } from "../lib/types";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Field, Notice } from "../components/shared";

const schema = z.object({
  email: z.string().email("Enter a valid email address."),
  password: z.string().min(1, "Enter your password."),
  first_name: z.string().optional(),
  role: z.enum(["attendee", "organizer"]),
});
type Credentials = z.infer<typeof schema>;
export function AuthPage({ register = false }: { register?: boolean }) {
  const { login } = useAuth();
  const [params] = useSearchParams();
  const [created, setCreated] = useState(false);
  const form = useForm<Credentials>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: "",
      password: "",
      first_name: "",
      role: "attendee",
    },
  });
  const submit = useMutation({
    mutationFn: async (values: Credentials) => {
      if (register && !created) {
        await api("/api/auth/register/", "POST", values);
        setCreated(true);
      }
      return login(values.email, values.password, params.get("next"));
    },
  });
  return (
    <main className="container auth-layout">
      <div className="auth-story">
        <span className="eyebrow">YOUR NEXT GREAT MEMORY</span>
        <h1>
          There’s a whole
          <br />
          world outside
          <br />
          your usual.
        </h1>
        <p>Find your people. Try something new. Take the ticket.</p>
        <Ticket className="auth-ticket" size={150} strokeWidth={1} />
        <span className="auth-caption">
          A good time starts with showing up.
        </span>
      </div>
      <div className="auth-form">
        <span className="eyebrow">
          {register ? "LET’S GET YOU OUT THERE" : "GOOD TO SEE YOU AGAIN"}
        </span>
        <h2>{register ? "Make yourself at home." : "Welcome back."}</h2>
        <p>
          {register
            ? "Create your account and make your next plan."
            : "Sign in to pick up where you left off."}
        </p>
        <form onSubmit={form.handleSubmit((values) => submit.mutate(values))}>
          {register ? (
            <Field label="First name">
              <Input
                autoComplete="given-name"
                {...form.register("first_name")}
              />
            </Field>
          ) : null}
          <Field
            label="Email address"
            error={form.formState.errors.email?.message}
          >
            <Input
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              {...form.register("email")}
            />
          </Field>
          <Field
            label="Password"
            error={form.formState.errors.password?.message}
          >
            <Input
              type="password"
              autoComplete={register ? "new-password" : "current-password"}
              {...form.register("password")}
            />
          </Field>
          {register ? (
            <>
              <small className="muted">
                Use at least 8 characters and avoid common passwords.
              </small>
              <Field label="I’m here to">
                <select {...form.register("role")}>
                  <option value="attendee">
                    Discover events and book tickets
                  </option>
                  <option value="organizer">Organize and manage events</option>
                </select>
              </Field>
            </>
          ) : null}
          <Notice error={submit.error} />
          {created && submit.isError ? (
            <Notice>
              Your account was created. Retry signing in with the same details.
            </Notice>
          ) : null}
          <Button type="submit" className="wide" disabled={submit.isPending}>
            {submit.isPending
              ? "One moment…"
              : register && !created
                ? "Create account"
                : "Sign in"}
            <ArrowRight size={17} />
          </Button>
        </form>
        <p className="auth-switch">
          {register ? "Already have an account?" : "New around here?"}{" "}
          <Link
            className="text-link"
            to={`${register ? "/login" : "/register"}${params.get("next") ? `?next=${encodeURIComponent(safeNext(params.get("next")))}` : ""}`}
          >
            {register ? "Sign in" : "Create an account"}
          </Link>
        </p>
        {!register ? (
          <details className="demo-details">
            <summary>Just exploring? Try a demo account</summary>
            <p>
              Attendee: <code>attendee@demo.dev</code>
              <br />
              Organizer: <code>organizer@demo.dev</code>
              <br />
              Password: <code>demo-pass-123</code>
            </p>
            <small>
              Use your own email to receive ticket emails. Demo checkout never
              charges money.
            </small>
          </details>
        ) : null}
      </div>
    </main>
  );
}

const profileSchema = z.object({
  first_name: z.string().max(150),
  last_name: z.string().max(150),
  phone: z.string().max(30),
  bio: z.string().max(2000),
  city: z.string().max(100),
});
export function ProfilePage() {
  const { user } = useAuth();
  const client = useQueryClient();
  const form = useForm<z.infer<typeof profileSchema>>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      first_name: user!.first_name,
      last_name: user!.last_name,
      ...user!.profile,
    },
  });
  const save = useMutation({
    mutationFn: (values: z.infer<typeof profileSchema>) => {
      const { first_name, last_name, ...profile } = values;
      return api<User>("/api/auth/me/", "PATCH", {
        first_name,
        last_name,
        profile,
      });
    },
    onSuccess: (updated) => client.setQueryData(["session"], updated),
  });
  return (
    <main className="container section narrow">
      <span className="eyebrow">A LITTLE ABOUT YOU</span>
      <h1>Your profile</h1>
      <p className="muted">
        {user!.email} · {user!.role}
      </p>
      <form
        className="panel form-stack"
        onSubmit={form.handleSubmit((values) => save.mutate(values))}
      >
        {(["first_name", "last_name", "phone", "city"] as const).map((name) => (
          <Field
            key={name}
            label={name.replace("_", " ")}
            error={form.formState.errors[name]?.message}
          >
            <Input {...form.register(name)} />
          </Field>
        ))}
        <Field label="Bio" error={form.formState.errors.bio?.message}>
          <textarea rows={4} {...form.register("bio")} />
        </Field>
        <Notice error={save.error} />
        {save.isSuccess ? <Notice>Profile saved.</Notice> : null}
        <Button disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save profile"}
        </Button>
      </form>
    </main>
  );
}
