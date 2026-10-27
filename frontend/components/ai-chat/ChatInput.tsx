"use client";

import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Send, Loader2 } from "lucide-react";

type ChatInputProps = {
  onSend: (text: string) => void;
  disabled?: boolean;
};

export default function ChatInput({
  onSend,
  disabled = false,
}: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const canSend = text.trim().length > 0 && !disabled;

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text]);

  const submit = () => {
    if (!canSend) return;
    onSend(text.trim());
    setText("");
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    submit();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="shrink-0 px-4 pb-4">
      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-2 rounded-2xl border border-slate-200/80 bg-white/90 p-2 pl-4 shadow-sm backdrop-blur-md transition-all duration-200 ease-in-out focus-within:border-slate-400 focus-within:bg-white focus-within:shadow-md"
      >
        <textarea
          ref={textareaRef}
          rows={1}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Message AI Assistant..."
          className="max-h-28 min-h-6 flex-1 resize-none border-none bg-transparent py-1 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:ring-0 disabled:opacity-50"
        />

        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white shadow-sm transition-all duration-200 enabled:cursor-pointer enabled:hover:bg-slate-800 enabled:active:scale-95 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400 disabled:shadow-none"
        >
          {disabled ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </form>
    </div>
  );
}
