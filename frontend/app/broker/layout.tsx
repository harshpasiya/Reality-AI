import AuthGuard from "@/components/auth/AuthGuard";

export default function BrokerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthGuard allowedRole="broker">{children}</AuthGuard>;
}
