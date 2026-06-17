"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS: [string, string][] = [
  ["/", "Hoje"],
  ["/farms", "Farms"],
  ["/cerebro", "Cérebro"],
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="nav">
      <span className="brand">Wraeclast</span>
      <div className="tabs">
        {TABS.map(([href, label]) => (
          <Link key={href} href={href} className={path === href ? "active" : ""}>
            {label}
          </Link>
        ))}
      </div>
    </nav>
  );
}
