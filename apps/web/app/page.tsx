"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Brand } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";
import type { IngestResult, InterestItem, StoryItem, StoryMember, User } from "@/lib/types";

function matchLabel(member: StoryMember): string {
  if (member.method === "content_hash") return "same text";
  if (member.method === "embedding" && member.similarity !== null) {
    return `${Math.round(member.similarity * 100)}% similar`;
  }
  return "";
}

function ingestSummary(result: IngestResult): string {
  const merged = result.joined_embedding + result.joined_content_hash;
  const parts = [
    `Fetched ${result.fetched} items from ${result.sources} sources, saved ${result.upserted} new or updated.`,
    `${result.stories_created} new stories${merged ? `, ${merged} merged into existing ones` : ""}.`,
  ];
  if (result.errors.length) parts.push(`${result.errors.length} source(s) failed.`);
  if (result.clustering_error) parts.push(`Grouping failed: ${result.clustering_error}`);
  return parts.join(" ");
}

function StoryCard({ story }: { story: StoryItem }) {
  const others = story.members.filter((member) => member.method !== "seed");
  const sources = Array.from(new Set(story.members.map((member) => member.source_name)));

  return (
    <article className="rounded-2xl border border-ink-700 bg-ink-900 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-paper-400">
        {sources.join(" · ")}
        {story.source_count > 1 ? (
          <span className="ml-2 rounded-full bg-ink-700 px-2 py-0.5 text-signal-400">
            {story.source_count} sources
          </span>
        ) : null}
      </p>
      <a
        href={story.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-1 block font-medium text-paper-50 hover:text-signal-400"
      >
        {story.title}
      </a>
      {story.excerpt ? <p className="mt-2 text-sm text-paper-400">{story.excerpt}</p> : null}
      {others.length ? (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-paper-400 hover:text-paper-50">
            Also covered by {others.length}
          </summary>
          <ul className="mt-2 space-y-1.5">
            {others.map((member) => (
              <li key={member.document_id} className="text-paper-400">
                <span className="text-paper-100">{member.source_name}</span>{" "}
                <a
                  href={member.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-signal-400"
                >
                  {member.title}
                </a>{" "}
                <span className="text-xs">({matchLabel(member)})</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </article>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [interests, setInterests] = useState<InterestItem[]>([]);
  const [stories, setStories] = useState<StoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);
  const [ingesting, setIngesting] = useState(false);

  async function loadStories() {
    const incoming = await api.stories();
    setStories(incoming.items);
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
        const incoming = await api.stories();
        if (!cancelled) {
          setUser(me);
          setInterests(saved.items);
          setStories(incoming.items);
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
      await loadStories();
      setIngestMessage(ingestSummary(result));
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
          <h1 className="font-display text-4xl text-paper-50">Stories, not duplicates.</h1>
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
          Coverage of the same event from different sources is grouped into one story. Ranking
          against your interests and summaries come next.
        </p>
        {ingestMessage ? <p className="mt-3 text-sm text-signal-400">{ingestMessage}</p> : null}
      </section>

      <section className="mt-10 space-y-4">
        {stories.length === 0 ? (
          <p className="text-paper-400">No stories yet. Click Fetch latest.</p>
        ) : (
          stories.map((story) => <StoryCard key={story.id} story={story} />)
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
