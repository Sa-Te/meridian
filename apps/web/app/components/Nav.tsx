"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/app/lib/cn";

const NAV_ITEMS = [
  { href: "/", label: "Chat" },
  { href: "/meetings", label: "Meetings" },
  { href: "/traces", label: "Traces" },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <nav className="mx-auto flex w-full max-w-2xl items-center justify-center gap-1 py-2">
      {NAV_ITEMS.map((item) => {
        const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-medium transition-colors",
              isActive
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
