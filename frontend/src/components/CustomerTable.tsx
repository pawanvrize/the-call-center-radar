"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import type { Customer } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

/**
 * 100 customers is too many to scan and too few to paginate, so filtering
 * happens client-side over the already-loaded list — instant, no round trip,
 * and no server state to get out of sync.
 */
export default function CustomerTable({ customers }: { customers: Customer[] }) {
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return customers;
    return customers.filter((c) => c.name.toLowerCase().includes(q));
  }, [customers, query]);

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search
          size={15}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by name…"
          aria-label="Search customers by name"
          className="w-full rounded-md border border-slate-200 bg-transparent py-2 pl-9 pr-3 text-sm outline-none placeholder:text-slate-400 focus:border-blue-500 dark:border-slate-800"
        />
      </div>

      <p className="text-sm text-slate-500">
        {visible.length === customers.length
          ? `${customers.length} customers`
          : `${visible.length} of ${customers.length} customers`}
      </p>

      {visible.length === 0 ? (
        <p className="text-sm text-slate-500">
          No customer matches “{query}”.
        </p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500 dark:border-slate-800 dark:bg-slate-900">
              <tr>
                <th className="px-4 py-2.5 font-medium">Name</th>
                <th className="px-4 py-2.5 font-medium">Calls</th>
                <th className="px-4 py-2.5 font-medium">Last contact</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-slate-100 last:border-b-0 hover:bg-slate-50 dark:border-slate-900 dark:hover:bg-slate-900/50"
                >
                  <td className="px-4 py-2.5">
                    <Link
                      href={`/customers/${encodeURIComponent(c.id)}`}
                      className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                    >
                      {c.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2.5 tabular-nums">{c.call_count}</td>
                  <td className="px-4 py-2.5 text-slate-500">
                    {c.last_contact ? formatDateTime(c.last_contact) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
