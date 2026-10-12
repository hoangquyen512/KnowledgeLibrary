import { redirectAnonymousHomeToLogin } from "@/lib/anonymous-home";

type HomePageProps = {
  searchParams: Promise<{ error?: string; next?: string }>;
};

export default async function HomePage({ searchParams }: HomePageProps) {
  const params = await searchParams;
  await redirectAnonymousHomeToLogin(params);
}
