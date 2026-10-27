"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  LayoutDashboard,
  LogOut,
  Plus,
  Search,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";

function getInitials(name: string | undefined) {
  if (!name) return "??";

  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

const noopSubscribe = () => () => {};

const itemClass =
  "flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-slate-700 transition hover:bg-slate-100";

export default function UserMenu() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);
  const [isOpen, setIsOpen] = useState(false);
  // The login state lives in localStorage, which the server can't see; wait
  // for the browser before choosing between "Log in" and the account menu.
  const isMounted = useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleDocumentClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleDocumentClick);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleDocumentClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  function handleLogout() {
    logout();
    setIsOpen(false);
    router.replace("/login");
  }

  if (!isMounted) {
    return <div className="h-11 w-16" aria-hidden="true" />;
  }

  if (!user) {
    return (
      <div className="flex items-center gap-2 text-sm font-medium">
        <Link
          href="/login"
          className="rounded-lg px-3 py-2 text-slate-700 hover:bg-slate-100"
        >
          Log in
        </Link>
        <Link
          href="/register"
          className="bg-accent hover:bg-accent-hover rounded-lg px-3 py-2 text-white"
        >
          Sign up
        </Link>
      </div>
    );
  }

  return (
    <div ref={menuRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label="Open account menu"
        aria-expanded={isOpen}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-lg bg-white/80 p-1 transition hover:bg-slate-100"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-sm font-medium">
          {getInitials(user.name)}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`h-4 w-4 text-slate-500 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {isOpen && (
        <div
          role="menu"
          className="absolute right-0 z-10 mt-2 w-56 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"
        >
          <div className="border-b border-slate-100 px-3 py-2">
            <p className="truncate text-sm font-medium text-slate-900">
              {user.name}
            </p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>

          {user.role === "broker" ? (
            <>
              <Link
                href="/broker/dashboard"
                role="menuitem"
                className={itemClass}
                onClick={() => setIsOpen(false)}
              >
                <LayoutDashboard aria-hidden="true" className="h-4 w-4" />
                Dashboard
              </Link>
              <Link
                href="/broker/listings/create"
                role="menuitem"
                className={itemClass}
                onClick={() => setIsOpen(false)}
              >
                <Plus aria-hidden="true" className="h-4 w-4" />
                Add listing
              </Link>
            </>
          ) : (
            <Link
              href="/"
              role="menuitem"
              className={itemClass}
              onClick={() => setIsOpen(false)}
            >
              <Search aria-hidden="true" className="h-4 w-4" />
              New search
            </Link>
          )}

          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className={itemClass}
          >
            <LogOut aria-hidden="true" className="h-4 w-4" />
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
