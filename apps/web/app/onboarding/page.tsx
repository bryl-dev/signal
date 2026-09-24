"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Brand } from "@/components/Brand";
import { ApiError, api } from "@/lib/api";
import type { TopicCategory } from "@/lib/types";

const MIN = 5;

export default function OnboardingPage() {
  const router = useRouter();
  const [categories, setCategories] = useState<TopicCategory[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [addingFor, setAddingFor] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await api.me();
        const catalog = await api.topics();
        const saved = await api.interests();
        if (!cancelled) {
          setCategories(catalog.categories);
          setSelected(new Set(saved.items.map((item) => item.topic_id)));
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login");
          return;
        }
        if (!cancelled) setError("Could not load topics.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function toggle(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function addCustom(categoryId: string) {
    const name = (drafts[categoryId] ?? "").trim();
    if (name.length < 2) return;
    setError(null);
    setAddingFor(categoryId);
    try {
      const topic = await api.createTopic(name, categoryId);
      setCategories((current) =>
        current.map((category) => {
          if (category.id !== categoryId) return category;
          if (category.topics.some((item) => item.id === topic.id)) return category;
          return { ...category, topics: [...category.topics, topic] };
        }),
      );
      setSelected((current) => new Set(current).add(topic.id));
      setDrafts((current) => ({ ...current, [categoryId]: "" }));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Could not add that topic.");
    } finally {
      setAddingFor(null);
    }
  }

  async function continueOnboarding() {
    setError(null);
    setPending(true);
    try {
      await api.saveInterests([...selected]);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save interests.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-6 py-12">
      <Brand compact />
      <h1 className="mt-10 font-display text-4xl text-paper-50">What should Signal watch?</h1>
      <p className="mt-3 max-w-xl text-paper-400">
        Pick at least {MIN} topics, or add your own under a category. Seed chips are suggestions, not
        a closed list.
      </p>
      <p className="mt-4 text-sm text-signal-400">
        {selected.size} selected {selected.size >= MIN ? "— ready" : `(need ${MIN - selected.size} more)`}
      </p>

      {loading ? <p className="mt-10 text-paper-400">Loading taxonomy…</p> : null}

      <div className="mt-8 space-y-10">
        {categories.map((category) => (
          <section key={category.id}>
            <h2 className="text-xs uppercase tracking-[0.2em] text-paper-400">{category.name}</h2>
            <div className="mt-3 flex flex-wrap gap-2">
              {category.topics.map((topic) => {
                const active = selected.has(topic.id);
                return (
                  <button
                    key={topic.id}
                    type="button"
                    title={topic.description ?? topic.name}
                    onClick={() => toggle(topic.id)}
                    className={`rounded-full border px-4 py-2 text-sm transition ${
                      active
                        ? "border-signal-400 bg-signal-400/15 text-paper-50"
                        : "border-ink-700 bg-ink-900 text-paper-400 hover:border-paper-400"
                    }`}
                  >
                    {topic.name}
                  </button>
                );
              })}
            </div>
            <form
              className="mt-3 flex max-w-md gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                void addCustom(category.id);
              }}
            >
              <input
                type="text"
                value={drafts[category.id] ?? ""}
                onChange={(event) =>
                  setDrafts((current) => ({ ...current, [category.id]: event.target.value }))
                }
                placeholder={`Add your own in ${category.name}`}
                minLength={2}
                maxLength={120}
                className="min-w-0 flex-1 rounded-xl border border-ink-700 bg-ink-900 px-3 py-2 text-sm text-paper-50 outline-none focus:border-signal-400"
              />
              <button
                type="submit"
                disabled={addingFor === category.id || (drafts[category.id] ?? "").trim().length < 2}
                className="rounded-xl border border-ink-700 px-3 py-2 text-sm text-paper-100 disabled:opacity-50"
              >
                {addingFor === category.id ? "Adding…" : "Add"}
              </button>
            </form>
          </section>
        ))}
      </div>

      {error ? <p className="mt-6 text-sm text-red-300">{error}</p> : null}

      <button
        type="button"
        disabled={selected.size < MIN || pending}
        onClick={continueOnboarding}
        className="mt-10 rounded-xl bg-signal-400 px-5 py-2.5 font-medium text-ink-950 disabled:opacity-50"
      >
        {pending ? "Saving…" : "Save interests"}
      </button>
    </main>
  );
}
