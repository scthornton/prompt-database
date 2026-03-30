import { getPrompts, getStats, getTechniques, getSources } from "@/lib/data";
import { PromptBrowser } from "./prompt-browser";

export default function Home() {
  const prompts = getPrompts();
  const stats = getStats();
  const techniques = getTechniques();
  const sources = getSources();

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">
          Prompt Injection Database
        </h1>
        <p className="mt-2 text-[var(--muted)]">
          {stats.total.toLocaleString()} curated attack prompts for defensive AI
          security research
        </p>
        <div className="mt-4 flex flex-wrap gap-4 text-sm">
          <span className="rounded bg-[var(--surface)] px-3 py-1">
            {Object.keys(stats.byTechnique).length} techniques
          </span>
          <span className="rounded bg-[var(--surface)] px-3 py-1">
            Avg sophistication: {stats.avgSophistication}
          </span>
          <span className="rounded bg-[var(--surface)] px-3 py-1">
            {stats.curated.toLocaleString()} curated
          </span>
          <span className="rounded bg-[var(--surface)] px-3 py-1">
            {Object.keys(stats.bySource).length} sources
          </span>
        </div>
      </header>

      <PromptBrowser
        prompts={prompts}
        techniques={techniques}
        sources={sources}
      />
    </main>
  );
}
