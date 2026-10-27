"use client";

import { FormEvent, useLayoutEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Sparkles, Loader2 } from "lucide-react";

import AuthGuard from "@/components/auth/AuthGuard";
import AppHeader from "@/components/AppHeader";
import { sendChatMessage } from "@/lib/api/chat";
import { useAuthStore } from "@/stores/authStore";

const SUGGESTIONS = [
  "3 BHK in Vesu, Surat under ₹80L",
  "Penthouse near Canal Road with terrace garden",
  "2 BHK furnished apartment near VIP Road",
  "Villa in Adajan with private parking",
];

export default function HomePage() {
  const router = useRouter();
  const user = useAuthStore((state) => state.user);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  useLayoutEffect(() => {
    if (user?.role === "broker") {
      router.replace("/broker/dashboard");
    }
  }, [router, user?.role]);

  const canSubmit = input.trim().length > 0;
  const hasInput = canSubmit && !isLoading;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const query = input.trim();
    if (!query || isLoading) return;

    setIsLoading(true);

    try {
      const response = await sendChatMessage({
        conversation_id: null,
        message: query,
        polygon: null,
      });

      if (response?.conversation_id) {
        router.push(`/chat/${response.conversation_id}`);
      } else {
        console.error("No conversation_id received in response.");
        setIsLoading(false);
      }
    } catch (error) {
      console.error("Chat failed:", error);
      setIsLoading(false);
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    setInput(suggestion);
  };

  if (user?.role === "broker") {
    return null;
  }

  return (
    <AuthGuard allowedRole={["customer", "broker"]}>
      <AppHeader />
      <section className="from-surface via-surface to-accent/5 relative flex min-h-[calc(100vh-4rem)] w-full flex-col items-center justify-center overflow-hidden bg-gradient-to-b px-4 py-12">
        <div className="bg-accent/15 absolute -top-40 left-1/2 -z-10 h-96 w-96 -translate-x-1/2 rounded-full blur-3xl" />

        <div className="w-full max-w-2xl px-4 text-center sm:px-6">
          <h1 className="text-text-primary text-3xl font-extrabold tracking-tight sm:text-5xl sm:leading-tight">
            Find your{" "}
            <span className="text-accent relative inline-block">
              perfect home
              <svg
                className="text-accent/60 absolute -bottom-1.5 left-0 h-2 w-full"
                viewBox="0 0 220 8"
                preserveAspectRatio="none"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M3 5C70 2, 150 6, 217 3.5"
                  stroke="currentColor"
                  strokeWidth="3"
                  strokeLinecap="round"
                />
              </svg>
            </span>
          </h1>

          {/* Subtitle */}
          <p className="text-text-secondary mt-4 text-base sm:text-lg">
            Describe what you&apos;re looking for in plain language and our AI
            will curate the best matching properties.
          </p>

          {/* Search Bar Container */}
          <form onSubmit={handleSubmit} className="mt-8 text-left">
            <div className="group border-accent/20 bg-surface/80 shadow-accent/5 focus-within:border-accent focus-within:ring-accent/10 hover:border-accent/40 relative flex items-center rounded-2xl border p-2 shadow-xl backdrop-blur-md transition-all duration-200 focus-within:ring-4">
              <div className="text-accent flex items-center pl-3">
                <Sparkles size={20} className="shrink-0" />
              </div>

              <input
                type="text"
                value={input}
                disabled={isLoading}
                onChange={(e) => setInput(e.target.value)}
                placeholder="e.g. 3 BHK in Vesu, Surat under ₹80L with parking..."
                aria-label="Describe your ideal home"
                className="text-text-primary placeholder:text-text-muted w-full border-none bg-transparent px-3 py-2 text-base outline-none disabled:opacity-50"
              />

              <button
                type="submit"
                disabled={!hasInput}
                aria-label="Search for homes"
                className={`flex h-11 shrink-0 items-center gap-2 rounded-xl px-4 font-medium text-white transition-all duration-200 ${
                  canSubmit
                    ? "bg-accent hover:bg-accent-hover shadow-accent/20 cursor-pointer shadow-md active:scale-95"
                    : "bg-accent-disabled cursor-not-allowed opacity-60"
                }`}
              >
                <span className="text-sm">Search</span>
                {isLoading ? (
                  <Loader2 size={18} className="animate-spin" />
                ) : (
                  <ArrowRight size={18} strokeWidth={2.5} />
                )}
              </button>
            </div>
          </form>

          {/* Quick Suggestion Pills */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
            <span className="text-text-muted text-xs font-medium">
              Try asking:
            </span>
            {SUGGESTIONS.map((suggestion, index) => (
              <button
                key={index}
                type="button"
                disabled={isLoading}
                onClick={() => handleSuggestionClick(suggestion)}
                className="border-accent-border/50 bg-surface/50 text-text-secondary hover:border-accent/40 hover:bg-accent/5 hover:text-accent rounded-lg border px-3 py-1.5 text-xs transition-all disabled:opacity-50"
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </section>
    </AuthGuard>
  );
}
