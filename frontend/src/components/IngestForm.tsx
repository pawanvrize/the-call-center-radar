"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Radar, Upload } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CallDetail } from "@/lib/types";

/** What the pipeline is doing, roughly, while the request is in flight.
 *  The API is a single synchronous call, so these are time-based rather than
 *  real progress events — labelled as an estimate rather than pretending to
 *  be telemetry we don't have. */
const STAGES = [
  "Splitting channels…",
  "Transcribing both speakers…",
  "Merging turns…",
  "Scoring mood, detecting the shift…",
  "Extracting intent and resolution…",
  "Verifying citations…",
];

export default function IngestForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [customer, setCustomer] = useState("");
  const [agent, setAgent] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file || busy) return;

    setBusy(true);
    setError(null);
    setStage(0);
    const ticker = setInterval(
      () => setStage((s) => Math.min(s + 1, STAGES.length - 1)),
      2200,
    );

    try {
      const body = new FormData();
      body.append("audio", file);
      body.append("customer_name", customer.trim() || "Unknown caller");
      body.append("agent_name", agent.trim() || "Unknown agent");

      const res = await fetch("/api/ingest", { method: "POST", body });
      const payload = await res.json();

      if (!res.ok) {
        throw new Error(
          typeof payload?.detail === "string"
            ? payload.detail
            : `Ingestion failed (${res.status})`,
        );
      }

      // Straight to the analysed call — the point of the demo is that the
      // dashboard treats a brand-new recording exactly like the other 1,441.
      router.push(`/calls/${encodeURIComponent((payload as CallDetail).id)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    } finally {
      clearInterval(ticker);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) setFile(dropped);
        }}
        className={cn(
          "flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-10 transition",
          dragging
            ? "border-blue-500 bg-blue-500/5"
            : "border-slate-300 hover:border-blue-400 dark:border-slate-700",
        )}
      >
        <Upload size={22} className="text-slate-400" />
        {file ? (
          <>
            <span className="font-medium">{file.name}</span>
            <span className="font-mono text-xs text-slate-500">
              {(file.size / 1024 / 1024).toFixed(1)} MB
            </span>
          </>
        ) : (
          <>
            <span className="text-sm font-medium">
              Drop a recording here, or click to choose
            </span>
            <span className="text-xs text-slate-500">
              Stereo audio — left channel agent, right channel customer
            </span>
          </>
        )}
      </button>

      <input
        ref={inputRef}
        type="file"
        accept="audio/*,.mp3,.wav"
        className="hidden"
        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
      />

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block">
          <span className="text-xs uppercase tracking-wide text-slate-500">
            Customer name
          </span>
          <input
            value={customer}
            onChange={(e) => setCustomer(e.target.value)}
            placeholder="Mary Smith"
            className="mt-1 w-full rounded-md border border-slate-200 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-800"
          />
        </label>
        <label className="block">
          <span className="text-xs uppercase tracking-wide text-slate-500">
            Agent name
          </span>
          <input
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            placeholder="Robert"
            className="mt-1 w-full rounded-md border border-slate-200 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-800"
          />
        </label>
      </div>

      <button
        type="submit"
        disabled={!file || busy}
        className="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {busy ? <Loader2 size={16} className="animate-spin" /> : <Radar size={16} />}
        {busy ? "Analysing…" : "Run the pipeline"}
      </button>

      {busy && (
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <p className="flex items-center gap-2 text-sm">
            <Loader2 size={14} className="animate-spin text-blue-500" />
            {STAGES[stage]}
          </p>
          <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
            <div
              style={{ width: `${((stage + 1) / STAGES.length) * 100}%` }}
              className="h-full rounded-full bg-blue-500 transition-all duration-700"
            />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Estimated stage — the API runs this as one synchronous call, so this
            is elapsed time rather than live progress.
          </p>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-4 text-sm">
          <p className="font-medium text-red-700 dark:text-red-400">
            Ingestion failed
          </p>
          <p className="mt-1 text-slate-600 dark:text-slate-400">{error}</p>
        </div>
      )}
    </form>
  );
}
