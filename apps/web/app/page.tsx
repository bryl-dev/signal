"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Brand } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";
import type { DocumentItem, InterestItem, User } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [interests, setInterests] = useState<InterestItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);

  async function loadDocuments() {
    const incoming = await api.documents();
    setDocuments(incoming.items);
  }

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
        const incoming = await api.documents();
        if (!cancelled) {
          setUser(me);
          setInterests(saved.items);
          setDocuments(incoming.items);
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

  async function fetchLatest() {
    setIngestMessage(null);
    setIngesting(true);
    try {
      const result = await api.ingest();
      await loadDocuments();
      const failed = result.errors.length;
      setIngestMessage(
        `Fetched ${result.fetched} items from ${result.sources} sources, saved ${result.upserted} new or updated.${
          failed ? ` ${failed} source(s) failed.` : ""
        }`,
      );
    } catch (err) {
      setIngestMessage(err instanceof ApiError ? err.message : "Ingest failed.");
    } finally {
      setIngesting(false);
    }
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
        <p className="text-xs uppercase tracking-[0.2em] text-signal-400">Incoming</p>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <h1 className="font-display text-4xl text-paper-50">Raw ingest, not a brief yet.</h1>
          <button
            type="button"
            onClick={fetchLatest}
            disabled={ingesting}
            className="rounded-xl bg-signal-400 px-4 py-2 text-sm font-medium text-ink-950 disabled:opacity-60"
          >
            {ingesting ? "Fetching…" : "Fetch latest"}
          </button>
        </div>
        <p className="mt-4 max-w-xl text-paper-400">
          These are normalized documents from RSS and Hacker News. Clustering, ranking, and
          summaries come next — you should still see duplicates.
        </p>
        {ingestMessage ? <p className="mt-3 text-sm text-signal-400">{ingestMessage}</p> : null}
      </section>

      <section className="mt-10 space-y-4">
        {documents.length === 0 ? (
          <p className="text-paper-400">No documents yet. Click Fetch latest.</p>
        ) : (
          documents.map((item) => (
            <article key={item.id} className="rounded-2xl border border-ink-700 bg-ink-900 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-paper-400">
                {item.source_name} · {item.content_type}
              </p>
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 block font-medium text-paper-50 hover:text-signal-400"
              >
                {item.title}
              </a>
              {item.excerpt ? <p className="mt-2 text-sm text-paper-400">{item.excerpt}</p> : null}
            </article>
          ))
        )}
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
