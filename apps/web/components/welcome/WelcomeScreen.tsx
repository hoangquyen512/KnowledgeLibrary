import type { WelcomeAuthProps } from "@/lib/auth-public";
import { KnowledgeHeroVisual } from "./KnowledgeHeroVisual";
import { LoginCard } from "./LoginCard";
import { WelcomeHeader } from "./WelcomeHeader";
import "./welcome.css";

export function WelcomeScreen(props: WelcomeAuthProps) {
  return (
    <main className="welcome-screen">
      <div className="welcome-bg" aria-hidden="true" />
      <KnowledgeHeroVisual />
      <WelcomeHeader />

      <div className="welcome-inner">
        <div className="welcome-viz-spacer" aria-hidden="true" />
        <LoginCard {...props} />
      </div>
    </main>
  );
}

/** Alias matching the welcome page composition name. */
export const WelcomePage = WelcomeScreen;
