"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Home, Sparkles } from "lucide-react";

export default function RealEstateAssistant() {
  const [input, setInput] = useState("");

  const hasInput = input.trim().length > 0;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const query = input.trim();

    if (!query) {
      return;
    }

    // Demo only.
    // Later, send this query to your AI API.
    console.log("Property search query:", query);
  }

  return (
    <section
      aria-label="Real Estate Assistant"
      className="border-border bg-surface fixed inset-x-0 bottom-0 z-10 w-full overflow-hidden rounded-t-3xl border shadow-[0_-12px_40px_rgba(28,35,50,0.12)] sm:inset-x-6 sm:bottom-6 sm:w-[420px] sm:rounded-2xl sm:shadow-[0_20px_60px_rgba(28,35,50,0.1)] lg:top-6 lg:right-auto lg:bottom-auto lg:left-6"
    >
      {/* Mobile drag indicator */}
      <div className="flex justify-center pt-3 lg:hidden">
        <div className="bg-border h-1 w-10 rounded-full" />
      </div>

      {/* Header - desktop/tablet */}
      <header className="border-border-subtle hidden h-16 items-center justify-between border-b px-5 sm:flex">
        <div className="flex items-center gap-3">
          <div className="bg-accent-soft text-accent flex size-9 items-center justify-center rounded-full">
            <Home size={18} strokeWidth={2} />
          </div>

          <span className="text-text-primary text-[15px] font-bold">
            Real Estate Assistant
          </span>
        </div>

        <span className="bg-accent-soft text-accent rounded-full px-3 py-1.5 text-xs leading-none font-bold">
          AI
        </span>
      </header>

      {/* Content */}
      <div className="px-5 pt-5 pb-[max(20px,env(safe-area-inset-bottom))] sm:px-7 sm:pt-7 sm:pb-6 lg:px-7 lg:pt-7">
        <h1 className="text-text-primary text-2xl leading-tight font-bold tracking-[-0.6px] sm:text-[28px]">
          Find your{" "}
          <span className="text-accent relative inline-block">
            perfect home
            <svg
              className="text-accent absolute -bottom-1 left-0 h-[6px] w-full"
              viewBox="0 0 220 8"
              preserveAspectRatio="none"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M3 5C 70 2, 150 6, 217 3.5"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeOpacity="0.5"
              />
            </svg>
          </span>
        </h1>

        {/* Desktop/tablet description */}
        <p className="text-text-secondary mt-2.5 mb-5 hidden text-[15px] leading-6 sm:block">
          Describe what you&apos;re looking for and I&apos;ll find matching
          homes.
        </p>

        {/* Mobile spacing */}
        <div className="h-4 sm:hidden" />

        {/* Search Form */}
        <form onSubmit={handleSubmit}>
          <div className="border-accent-border bg-surface flex h-[60px] items-center gap-3 rounded-xl border py-2 pr-2 pl-4 shadow-[0_0_0_4px_rgba(111,99,200,0.08),0_8px_20px_rgba(111,99,200,0.08)]">
            <Sparkles
              size={18}
              strokeWidth={2}
              className="text-accent shrink-0"
            />

            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Describe your ideal home..."
              aria-label="Describe your ideal home"
              className="text-text-primary placeholder:text-text-muted min-w-0 flex-1 border-none bg-transparent text-[15px] outline-none"
            />

            <button
              type="submit"
              aria-label="Search for homes"
              disabled={!hasInput}
              className={`flex size-11 shrink-0 items-center justify-center rounded-lg text-white transition-colors duration-150 ${
                hasInput
                  ? "bg-accent hover:bg-accent-hover cursor-pointer"
                  : "bg-accent-disabled cursor-not-allowed"
              } `}
            >
              <ArrowRight size={20} strokeWidth={2} />
            </button>
          </div>
        </form>

        {/* Example - desktop/tablet only */}
        <p className="text-text-muted mt-3 hidden text-xs leading-5 sm:block">
          Example: 3 BHK in Vesu, Surat under ₹80L with parking
        </p>
      </div>
    </section>
  );
}
