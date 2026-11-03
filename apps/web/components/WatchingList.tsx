"use client";

import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import type { InterestItem } from "@/lib/types";

function weightNote(item: InterestItem): string | null {
  if (!item.votes) return null;
  const direction = item.votes > 0 ? "up" : "down";
  return `Weight ${item.effective_weight.toFixed(2)} (from ${item.weight.toFixed(2)}): your votes moved it ${direction}.`;
}

export function WatchingList({
  interests,
  onSaved,
  onChanged,
}: {
  interests: InterestItem[];
  onSaved: (item: InterestItem) => void;
  onChanged: () => Promise<void>;
}) {
  const [openId, setOpenId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const open = interests.find((item) => item.topic_id === openId) ?? null;

  function toggle(item: InterestItem) {
    setError(null);
    if (openId === item.topic_id) {
      setOpenId(null);
      return;
    }
    setOpenId(item.topic_id);
    setDraft(item.aliases.join(", "));
  }

  async function save() {
    if (!open) return;
    setError(null);
    setSaving(true);
    try {
      const aliases = draft
        .split(",")
        .map((alias) => alias.trim())
        .filter(Boolean);
      onSaved(await api.updateInterest(open.topic_id, aliases));
      await onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save aliases.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mt-12">
      <h2 className="text-xs uppercase tracking-[0.2em] text-paper-400">Watching</h2>
      <p className="mt-2 text-sm text-paper-400">
        Click a topic to add other names for it, so stories that never say the topic&apos;s name
        still match.
      </p>
      <ul className="mt-4 flex flex-wrap gap-2">
        {interests.map((item) => (
          <li key={item.topic_id}>
            <button
              type="button"
              onClick={() => toggle(item)}
              aria-expanded={openId === item.topic_id}
              className={`rounded-full border px-3 py-1.5 text-sm ${
                openId === item.topic_id
                  ? "border-signal-400 bg-signal-400/15 text-paper-50"
                  : "border-ink-700 bg-ink-900 text-paper-100 hover:border-paper-400"
              }`}
            >
              {item.name}
              {item.votes ? (
                <span className="ml-1.5 text-xs text-paper-400">
                  {item.votes > 0 ? "▲" : "▼"}
                  {Math.abs(item.votes)}
                </span>
              ) : null}
            </button>
          </li>
        ))}
      </ul>

      {open ? (
        <form
          className="mt-4 rounded-2xl border border-ink-700 bg-ink-900 p-4 text-sm"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <p className="text-paper-100">{open.name}</p>
          {open.topic_aliases.length ? (
            <p className="mt-2 text-paper-400">Built in: {open.topic_aliases.join(", ")}</p>
          ) : null}
          {weightNote(open) ? <p className="mt-1 text-paper-400">{weightNote(open)}</p> : null}
          <label className="mt-3 block text-paper-400" htmlFor="aliases">
            Your aliases, comma-separated (3 characters or fewer match exact case, so “LoL” won’t
            catch “lol”)
          </label>
          <div className="mt-2 flex gap-2">
            <input
              id="aliases"
              type="text"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="e.g. MH Wilds, MHWilds"
              className="min-w-0 flex-1 rounded-xl border border-ink-700 bg-ink-950 px-3 py-2 text-paper-50 outline-none focus:border-signal-400"
            />
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-signal-400 px-3 py-2 font-medium text-ink-950 disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
          {error ? <p className="mt-2 text-red-400">{error}</p> : null}
        </form>
      ) : null}
    </section>
  );
}
