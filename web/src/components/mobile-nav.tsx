"use client";

import { usePathname, useRouter } from "next/navigation";
import { LayoutDashboard, Receipt, BookOpen, Mic } from "lucide-react";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Tasks", icon: LayoutDashboard },
  { href: "/finance", label: "Finance", icon: Receipt },
  { href: "/notes", label: "Notes", icon: BookOpen },
  { href: "/voice", label: "Voice", icon: Mic },
];

export function MobileNav() {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 md:hidden">
      <div className="flex h-16 items-center justify-around px-2 safe-area-bottom">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <button
              key={item.href}
              onClick={() => router.push(item.href)}
              className={`flex flex-col items-center justify-center gap-0.5 rounded-lg px-3 py-2 min-w-[64px] min-h-[44px] transition-colors ${
                isActive
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-5 w-5" />
              <span className="text-[10px] font-medium leading-none">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
