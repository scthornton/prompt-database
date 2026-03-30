"use client";

import { useState, useMemo } from "react";
import type { Prompt } from "@/lib/data";

interface Props {
  prompts: Prompt[];
  techniques: string[];
  sources: string[];
}

export function PromptBrowser({ prompts, techniques, sources }: Props) {
  const [query, setQuery] = useState("");
  const [technique, setTechnique] = useState("");
  const [source, setSource] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [selected, setSelected] = useState<Prompt | null>(null);
  const [page, setPage] = useState(0);

  const PAGE_SIZE = 25;

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return prompts.filter((p) => {
      if (q && !p.content.toLowerCase().includes(q)) return false;
      if (technique && p.technique !== technique) return false;
      if (source && p.source !== source) return false;
      if (p.sophistication_score < minScore) return false;
      return true;
    });
  }, [prompts, query, technique, source, minScore]);

  const pageCount = Math.ceil(filtered.length / PAGE_SIZE);
  const visible = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function resetFilters() {
    setQuery("");
    setTechnique("");
    setSource("");
    setMinScore(0);
    setPage(0);
  }

  return (
    <div>
      {/* Filters */}
      <div className="mb-6 space-y-3">
        <input
          type="text"
          placeholder="Search prompt content..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
          className="w-full rounded border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 text-sm placeholder-[var(--muted)] outline-none focus:border-[var(--accent)]"
        />

        <div className="flex flex-wrap gap-3">
          <select
            value={technique}
            onChange={(e) => {
              setTechnique(e.target.value);
              setPage(0);
            }}
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          >
            <option value="">All techniques</option>
            {techniques.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>

          <select
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setPage(0);
            }}
            className="rounded border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
          >
            <option value="">All sources</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>

          <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
            Min score:
            <input
              type="range"
              min={0}
              max={15}
              value={minScore}
              onChange={(e) => {
                setMinScore(Number(e.target.value));
                setPage(0);
              }}
              className="w-24"
            />
            <span className="mono w-6 text-[var(--fg)]">{minScore}</span>
          </label>

          <button
            onClick={resetFilters}
            className="rounded border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)] hover:bg-[var(--surface-hover)]"
          >
            Reset
          </button>
        </div>

        <p className="text-sm text-[var(--muted)]">
          {filtered.length.toLocaleString()} prompts match
        </p>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="mb-6 rounded border border-[var(--border)] bg-[var(--surface)] p-4">
          <div className="mb-3 flex items-start justify-between">
            <div>
              <span className="mono text-sm text-[var(--accent)]">
                #{selected.id}
              </span>
              <span className="ml-3 rounded bg-[var(--accent-muted)] px-2 py-0.5 text-xs font-medium text-[var(--fg)]">
                {selected.technique.replace(/_/g, " ")}
              </span>
              <span className="ml-2 rounded bg-[var(--surface-hover)] px-2 py-0.5 text-xs">
                {selected.complexity}
              </span>
              <span className="ml-2 text-xs text-[var(--muted)]">
                score: {selected.sophistication_score}
              </span>
            </div>
            <button
              onClick={() => setSelected(null)}
              className="text-[var(--muted)] hover:text-[var(--fg)]"
            >
              &times;
            </button>
          </div>

          <pre className="mono max-h-80 overflow-auto whitespace-pre-wrap text-sm leading-relaxed">
            {selected.content}
          </pre>

          <div className="mt-3 flex flex-wrap gap-2">
            {selected.tags.map((tag) => (
              <span
                key={tag}
                className="rounded bg-[var(--bg)] px-2 py-0.5 text-xs text-[var(--muted)]"
              >
                {tag}
              </span>
            ))}
          </div>

          {selected.owasp_ids.length > 0 && (
            <div className="mt-2 text-xs text-[var(--muted)]">
              OWASP: {selected.owasp_ids.join(", ")}
            </div>
          )}

          <div className="mt-2 text-xs text-[var(--muted)]">
            Source: {selected.source}
          </div>
        </div>
      )}

      {/* Prompt list */}
      <div className="space-y-1">
        {visible.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p)}
            className={`w-full rounded px-4 py-3 text-left transition-colors ${
              selected?.id === p.id
                ? "border border-[var(--accent)] bg-[var(--surface)]"
                : "border border-transparent hover:bg-[var(--surface)]"
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="mono shrink-0 text-xs text-[var(--muted)]">
                #{p.id}
              </span>
              <span className="shrink-0 rounded bg-[var(--accent-muted)] px-1.5 py-0.5 text-xs">
                {p.technique.replace(/_/g, " ")}
              </span>
              <span className="mono shrink-0 text-xs text-[var(--muted)]">
                {p.sophistication_score}
              </span>
              <span className="truncate text-sm">
                {p.content.slice(0, 120).replace(/\n/g, " ")}
              </span>
            </div>
          </button>
        ))}
      </div>

      {/* Pagination */}
      {pageCount > 1 && (
        <div className="mt-6 flex items-center justify-center gap-4">
          <button
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-30"
          >
            Previous
          </button>
          <span className="text-sm text-[var(--muted)]">
            Page {page + 1} of {pageCount}
          </span>
          <button
            disabled={page >= pageCount - 1}
            onClick={() => setPage(page + 1)}
            className="rounded border border-[var(--border)] px-3 py-1.5 text-sm disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
