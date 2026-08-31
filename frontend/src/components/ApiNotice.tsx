import { AlertTriangle } from "lucide-react";

/**
 * Shown wherever the API couldn't supply data. Deliberately explicit rather
 * than a blank page or fake placeholder rows: while the backend endpoints are
 * still 501s, "nothing here yet and here's why" is the honest state.
 */
export default function ApiNotice({ error }: { error: string }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-sm">
      <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-500" />
      <div>
        <p className="font-medium text-amber-700 dark:text-amber-400">
          No data from the API
        </p>
        <p className="mt-1 font-mono text-xs text-slate-500">{error}</p>
      </div>
    </div>
  );
}
