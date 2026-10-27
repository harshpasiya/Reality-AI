"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { UserRole } from "@/lib/api/auth";
import { useAuthStore } from "@/stores/authStore";

interface AuthGuardProps {
  children: React.ReactNode;
  allowedRole: UserRole | UserRole[];
}

export default function AuthGuard({ children, allowedRole }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [hasHydrated, setHasHydrated] = useState(false);

  const accessToken = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);

  useEffect(() => {
    const unsubHydrate = useAuthStore.persist.onFinishHydration(() => {
      setHasHydrated(true);
    });

    if (useAuthStore.persist.hasHydrated()) {
      queueMicrotask(() => setHasHydrated(true));
    }

    return () => unsubHydrate();
  }, []);

  const roles = Array.isArray(allowedRole) ? allowedRole : [allowedRole];
  const isAuthorized = user !== null && roles.includes(user.role);

  useEffect(() => {
    if (!hasHydrated) return;

    if (!accessToken) {
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
      return;
    }

    if (!isAuthorized) {
      router.replace(user?.role === "broker" ? "/broker" : "/");
    }
  }, [hasHydrated, accessToken, isAuthorized, user, pathname, router]);

  if (!hasHydrated || !accessToken || !isAuthorized) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-zinc-500">Checking authentication...</p>
      </div>
    );
  }

  return <>{children}</>;
}
