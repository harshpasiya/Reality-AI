import {
  Bot,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

type ChatHeaderProps = {
  isCollapsed: boolean;
  onToggle: () => void;
};

export default function ChatHeader({ isCollapsed, onToggle }: ChatHeaderProps) {
  const MobileIcon = isCollapsed ? ChevronUp : ChevronDown;
  const DesktopIcon = isCollapsed ? ChevronRight : ChevronLeft;

  return (
    <header className="flex h-(--chat-header-h) shrink-0 items-center justify-between border-b border-slate-300/50 px-4">
      <div
        className={cn(
          "flex items-center gap-3 transition-opacity duration-300",
          isCollapsed && "lg:opacity-0",
        )}
      >
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#1E1E24] text-white">
          <Bot className="h-5 w-5" />
        </div>

        <div>
          <h2 className="text-sm font-semibold text-slate-900">Reality AI</h2>
          <p className="text-xs text-slate-500">Finding your dream home</p>
        </div>
      </div>
      <button
        type="button"
        onClick={onToggle}
        aria-label={isCollapsed ? "Expand chat" : "Collapse chat"}
        aria-expanded={!isCollapsed}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
      >
        <MobileIcon className="h-5 w-5 lg:hidden" />
        <DesktopIcon className="hidden h-5 w-5 lg:block" />
      </button>
    </header>
  );
}
