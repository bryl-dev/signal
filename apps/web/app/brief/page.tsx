"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Brand } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";
import type { Brief, BriefItem } from "@/lib/types";

function formatTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function Citation({ number, item }: { number: number; item: BriefItem }) {
  const source = item.sources[number - 1];
  if (!source) return null;
  return (
    <a
      href={source.url}
      target="_blank"
      rel="noopener noreferrer"
      title={`${source.source_name}: ${source.title}`}
      className="ml-0.5 align-super text-[0.7rem] text-signal-400 hover:underline"
    >
      [{number}]
    </a>
  );
}

function BriefCard({ item }: { item: BriefItem }) {
  const topics = item.reasons.filter((reason) => reason.kind === "topic");
  return (
    <article className="rounded-2xl border border-ink-700 bg-ink-900 p-5">
      <p className="text-xs uppercase tracking-[0.16em] text-paper-400">
        {String(item.position + 1).padStart(2, "0")}
        {item.method === "extractive" ? (
          <span
            className="ml-2 rounded-full bg-ink-700 px-2 py-0.5 normal-case tracking-normal"
            title={
              item.bullets.length
                ? "The model was unavailable or its summary failed the source checks, so this is the lead article's own opening."
                : "The sources are links without article text, so there was nothing to summarize."
            }
          >
            {item.bullets.length ? "excerpt, not summarized" : "link only"}
          </span>
        ) : null}
      </p>
      <h2 className="mt-1 font-display text-2xl text-paper-50">{item.headline}</h2>
      <ul className="mt-3 space-y-2 text-paper-100">
        {item.bullets.map((bullet) => (
          <li key={bullet.text} className="flex gap-2">
            <span className="text-signal-400">·</span>
            <span>
              {bullet.text}
              {bullet.citations.map((number) => (
                <Citation key={number} number={number} item={item} />
              ))}
            </span>
          </li>
        ))}
      </ul>
      {topics.length ? (
        <ul className="mt-4 flex flex-wrap gap-1.5" aria-label="Why this is here">
          {topics.map((reason) => (
            <li
              key={reason.label}
              className="rounded-full border border-signal-400/40 px-2 py-0.5 text-xs text-signal-400"
            >
              {reason.label}
            </li>
          ))}
        </ul>
      ) : null}
      <ol className="mt-4 space-y-1 border-t border-ink-700 pt-3 text-sm text-paper-400">
        {item.sources.map((source, index) => (
          <li key={source.document_id}>
            <span className="text-paper-100">[{index + 1}]</span> {source.source_name} ·{" "}
            <a
              href={source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-signal-400"
            >
              {source.title}
            </a>
          </li>
        ))}
      </ol>
    </article>
  );
}

export default function BriefPage() {
  const router = useRouter();
  const [brief, setBrief] = useState<Brief | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const latest = await api.brief();
        if (!cancelled) {
          setBrief(latest.brief);
          setLoaded(true);
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError("Could not load your brief.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function generate() {
    setError(null);
    setGenerating(true);
    try {
      setBrief(await api.generateBrief());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not generate a brief.");
    } finally {
      setGenerating(false);
    }
  }

  const fallbacks = brief?.items.filter((item) => item.method === "extractive").length ?? 0;

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-6 py-10">
      <header className="flex items-center justify-between">
        <Brand compact />
        <nav className="flex items-center gap-4 text-sm text-paper-400">
          <Link href="/" className="hover:text-paper-50">
            Feed
          </Link>
          <Link href="/onboarding" className="hover:text-paper-50">
            Interests
          </Link>
        </nav>
      </header>

      <section className="mt-14">
        <p className="text-xs uppercase tracking-[0.2em] text-signal-400">Morning brief</p>
        <div className="mt-3 flex flex-wrap items-end justify-between gap-4">
          <h1 className="font-display text-4xl text-paper-50">
            {brief ? formatTime(brief.created_at) : "Your brief"}
          </h1>
          <button
            type="button"
            onClick={generate}
            disabled={generating || !loaded}
            className="rounded-xl bg-signal-400 px-4 py-2 text-sm font-medium text-ink-950 disabled:opacity-60"
          >
            {generating ? "Writing… (can take a minute)" : brief ? "Regenerate" : "Generate brief"}
          </button>
        </div>
        <p className="mt-4 max-w-xl text-paper-400">
          Your top stories, summarized only from the articles that covered them. Every line cites
          its sources, and lines that can&apos;t be traced back to a source are thrown out.
        </p>
        {error ? <p className="mt-3 text-sm text-red-400">{error}</p> : null}
        {brief?.llm_error && fallbacks ? (
          <p className="mt-3 text-sm text-paper-400">
            {fallbacks} of {brief.items.length} stories show an excerpt instead of a summary.{" "}
            {brief.llm_error.includes("Ollama request failed")
              ? `Is Ollama running? (${brief.llm_error.slice(0, 160)})`
              : "The model's summaries for them didn't pass the source checks."}
          </p>
        ) : null}
      </section>

      <section className="mt-10 space-y-4">
        {!loaded && !error ? <p className="text-paper-400">Loading…</p> : null}
        {loaded && !brief ? (
          <p className="text-paper-400">No brief yet. Generate one from your current feed.</p>
        ) : null}
        {brief && brief.items.length === 0 ? (
          <p className="text-paper-400">
            Nothing in your feed matched your interests. Fetch latest on the{" "}
            <Link href="/" className="text-signal-400">
              feed
            </Link>{" "}
            first.
          </p>
        ) : null}
        {brief?.items.map((item) => <BriefCard key={item.position} item={item} />)}
      </section>

      {brief ? (
        <p className="mt-10 text-xs text-paper-400">
          Written by {brief.model} running locally. Summaries can still get details wrong; the
          cited articles are the source of truth.
        </p>
      ) : null}
    </main>
  );
}
