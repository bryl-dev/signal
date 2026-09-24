"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Brand } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const user =
        mode === "login" ? await api.login(email, password) : await api.register(email, password);
      router.push(user.onboarded ? "/" : "/onboarding");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof TypeError) {
        setError("Can't reach the API. Is it running on port 8000, and is Postgres up?");
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-md flex-col justify-center px-6 py-16">
      <Brand />
      <h1 className="mt-10 font-display text-4xl leading-tight text-paper-50">
        {mode === "login" ? "Welcome back." : "Create your brief."}
      </h1>
      <p className="mt-3 text-paper-400">
        One feed for the topics you already care about. No tab-hopping.
      </p>

      <div className="mt-8 flex gap-2 rounded-full bg-ink-800 p-1 text-sm">
        <button
          type="button"
          onClick={() => setMode("login")}
          className={`flex-1 rounded-full px-4 py-2 ${
            mode === "login" ? "bg-ink-700 text-paper-50" : "text-paper-400"
          }`}
        >
          Sign in
        </button>
        <button
          type="button"
          onClick={() => setMode("register")}
          className={`flex-1 rounded-full px-4 py-2 ${
            mode === "register" ? "bg-ink-700 text-paper-50" : "text-paper-400"
          }`}
        >
          Create account
        </button>
      </div>

      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm text-paper-400">
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1.5 w-full rounded-xl border border-ink-700 bg-ink-900 px-3 py-2.5 text-paper-50 outline-none focus:border-signal-400"
          />
        </label>
        <label className="block text-sm text-paper-400">
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="mt-1.5 w-full rounded-xl border border-ink-700 bg-ink-900 px-3 py-2.5 text-paper-50 outline-none focus:border-signal-400"
          />
        </label>
        {error ? <p className="text-sm text-red-300">{error}</p> : null}
        <button
          type="submit"
          disabled={pending}
          className="w-full rounded-xl bg-signal-400 px-4 py-2.5 font-medium text-ink-950 disabled:opacity-60"
        >
          {pending ? "Working…" : mode === "login" ? "Enter Signal" : "Get started"}
        </button>
      </form>

      <p className="mt-8 text-center text-sm text-paper-400">
        <Link href="/" className="underline decoration-ink-700 underline-offset-4">
          Back to home
        </Link>
      </p>
    </main>
  );
}
