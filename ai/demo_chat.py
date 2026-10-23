"""Interactive console chat demo for Reality AI.

A live, conversational demo of the full RAG pipeline:
  query → semantic retrieval → fine-tuned model → response

Perfect for pitching — shows the entire AI track working end-to-end
in a single terminal window.

Usage (from repo root, with .venv active and Docker DB running):
    python -m ai.demo_chat

Commands during the chat:
    /quit or /exit   — end the session
    /clear           — clear conversation history
    /listings        — show the raw listings retrieved for the last query
    /reload          — hot-reload the model (after retraining)
"""

from __future__ import annotations

import logging
import sys
import time

# Suppress noisy library logs during the demo
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logging.getLogger("ai").setLevel(logging.WARNING)

# ── Banner ───────────────────────────────────────────────────────────────
BANNER = r"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     ██████╗ ███████╗ █████╗ ██╗     ██╗████████╗██╗   ██╗            ║
║     ██╔══██╗██╔════╝██╔══██╗██║     ██║╚══██╔══╝╚██╗ ██╔╝            ║
║     ██████╔╝█████╗  ███████║██║     ██║   ██║    ╚████╔╝             ║
║     ██╔══██╗██╔══╝  ██╔══██║██║     ██║   ██║     ╚██╔╝              ║
║     ██║  ██║███████╗██║  ██║███████╗██║   ██║      ██║               ║
║     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝╚═╝   ╚═╝      ╚═╝               ║
║                        A I   A S S I S T A N T                       ║
║                                                                      ║
║   AI-powered property search for Surat, Gujarat                      ║
║   Type a question to get started. /quit to exit.                     ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""


def main() -> None:
    print(BANNER)
    print("  Loading the AI model (this takes ~30 seconds on first run)...\n")

    # Import here so the banner shows before the slow model load
    from ai.inference.generate_response import generate_response
    from ai.inference.load_model import get_model, reload_model
    from ai.rag.retriever import search

    # Trigger the model load now so it's cached for the first query
    t0 = time.time()
    try:
        get_model()
    except Exception as e:
        print(f"\n  [ERROR] Failed to load model: {e}")
        print("  Make sure the adapter is at: ai/finetune/adapters/reality-ai-lora/")
        sys.exit(1)

    load_time = time.time() - t0
    print(f"  ✓ Model loaded in {load_time:.1f}s\n")
    print("─" * 70)

    history: list[dict] = []
    last_listings: list[dict] = []

    while True:
        try:
            user_input = input("\n  You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Goodbye! 👋\n")
            break

        if not user_input:
            continue

        # ── Commands ─────────────────────────────────────────────────
        if user_input.lower() in ("/quit", "/exit"):
            print("\n  Goodbye! 👋\n")
            break

        if user_input.lower() == "/clear":
            history.clear()
            print("  ✓ Conversation history cleared.")
            continue

        if user_input.lower() == "/listings":
            if not last_listings:
                print("  (no listings retrieved yet — ask a question first)")
            else:
                print(f"\n  Last retrieved listings ({len(last_listings)}):")
                for i, l in enumerate(last_listings, 1):
                    price = l.get("price")
                    if price and price >= 1_00_00_000:
                        price_str = f"Rs.{price / 1_00_00_000:.2f} Cr"
                    elif price and price >= 1_00_000:
                        price_str = f"Rs.{price / 1_00_000:.1f} L"
                    elif price:
                        price_str = f"Rs.{price:,.0f}"
                    else:
                        price_str = "N/A"
                    print(f"    {i}. {l['title']}  ({price_str}, score: {l['distance_score']:.4f})")
            continue

        if user_input.lower() == "/reload":
            print("  Reloading model...")
            reload_model()
            get_model()
            print("  ✓ Model reloaded.")
            continue

        # ── RAG Pipeline ─────────────────────────────────────────────
        # Step 1: Retrieve
        t_retrieval = time.time()
        try:
            listings = search(user_input, top_k=5)
        except Exception as e:
            print(f"\n  [Retrieval error] {e}")
            listings = []
        retrieval_ms = (time.time() - t_retrieval) * 1000
        last_listings = listings

        # Step 2: Generate
        t_gen = time.time()
        reply = generate_response(user_input, listings, history or None)
        gen_ms = (time.time() - t_gen) * 1000

        # Step 3: Update history
        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

        # Step 4: Display
        print(f"\n  Assistant: {reply}")
        print(f"\n  ┌─ retrieval: {retrieval_ms:.0f}ms ({len(listings)} listings) │ generation: {gen_ms:.0f}ms ─┐")


if __name__ == "__main__":
    main()
