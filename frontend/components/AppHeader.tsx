import Link from "next/link";
import UserMenu from "./UserMenu";

interface AppHeaderProps {
  homeHref?: string;
}

export default function AppHeader({ homeHref = "/" }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link href={homeHref} className="text-lg font-semibold tracking-tight">
          Reality AI
        </Link>

        <UserMenu />
      </div>
    </header>
  );
}
