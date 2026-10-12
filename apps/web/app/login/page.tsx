import { SimpleLoginScreen } from "@/components/auth/SimpleLoginScreen";
import { requireAnonymousWelcome } from "@/lib/welcome-session";

type LoginPageProps = {
  searchParams: Promise<{ error?: string; next?: string }>;
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const params = await searchParams;
  const login = await requireAnonymousWelcome(params);
  return <SimpleLoginScreen {...login} />;
}
