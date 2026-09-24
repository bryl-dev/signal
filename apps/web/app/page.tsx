"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Brand } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";
import type { InterestItem, User } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [interests, setInterests] = useState<InterestItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.me();
        if (!me.onboarded) {
          router.replace("/onboarding");
          return;
        }
        const saved = await api.interests();
        if (!cancelled) {
          setUser(me);
          setInterests(saved.items);
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError("Could not load your session.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function signOut() {
    await api.logout();
    router.replace("/login");
  }

  if (error) {
    return (
      <main className="mx-auto max-w-xl px-6 py-24 text-center text-paper-400">
        {error}{" "}
        <Link href="/login" className="text-signal-400">
          Sign in
        </Link>
      </main>
    );
  }

  if (!user) {
    return <main className="px-6 py-24 text-center text-paper-400">Loading your brief…</main>;
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-6 py-10">
      <header className="flex items-center justify-between">
        <Brand compact />
        <div className="flex items-center gap-4 text-sm text-paper-400">
          <span>{user.email}</span>
          <Link href="/onboarding" className="hover:text-paper-50">
            Interests
          </Link>
          <button type="button" onClick={signOut} className="hover:text-paper-50">
            Sign out
          </button>
        </div>
      </header>

      <section className="mt-14">
        <p className="text-xs uppercase tracking-[0.2em] text-signal-400">Today’s Brief</p>
        <h1 className="mt-3 font-display text-4xl text-paper-50">Nothing to brief yet.</h1>
        <p className="mt-4 max-w-xl text-paper-400">
          Your interests are saved. Ingestion, clustering, and ranking land in the next milestone —
          this empty state is intentional, not a broken feed.
        </p>
      </section>

      <section className="mt-12">
        <h2 className="text-xs uppercase tracking-[0.2em] text-paper-400">Watching</h2>
        <ul className="mt-4 flex flex-wrap gap-2">
          {interests.map((item) => (
            <li
              key={item.topic_id}
              className="rounded-full border border-ink-700 bg-ink-900 px-3 py-1.5 text-sm text-paper-100"
            >
              {item.name}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
