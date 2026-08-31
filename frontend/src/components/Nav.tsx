"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Headphones, PhoneCall, Radar, TrendingUp, Upload, Users } from "lucide-react";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/", label: "Attention", icon: Activity },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/trends", label: "Trends", icon: TrendingUp },
  { href: "/agents", label: "Agents", icon: Headphones },
  { href: "/repeat-contacts", label: "Repeats", icon: PhoneCall },
  { href: "/ingest", label: "Analyse a call", icon: Upload },
] as const;

export default function Nav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
      <nav className="mx-auto flex max-w-6xl items-center gap-1 px-6 py-3">
        <Link href="/" className="mr-6 flex items-center gap-2 font-semibold">
          <Radar size={18} className="text-blue-500" />
          Call-Centre Radar
        </Link>
        {LINKS.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : (pathname ?? "").startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition",
                active
                  ? "bg-blue-500/10 font-medium text-blue-600 dark:text-blue-400"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-900",
              )}
            >
              <Icon size={15} />
              {label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
