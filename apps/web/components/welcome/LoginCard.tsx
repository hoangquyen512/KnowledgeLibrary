import Image from "next/image";
import { BRAND } from "@/components/brand/tokens";
import { googleLoginHref, type WelcomeAuthProps } from "@/lib/auth-public";
import { GoogleSignInButton } from "./GoogleSignInButton";
import { SecurityNote } from "./SecurityNote";
import { SourcePills } from "./SourcePills";

export function LoginCard({ googleConfigured, error, nextPath }: WelcomeAuthProps) {
  return (
    <section className="welcome-card" id="product" aria-labelledby="welcome-headline">
      <div className="welcome-mascot-wrap">
        <Image
          src={BRAND.paths.antFull}
          alt=""
          width={140}
          height={148}
          className="welcome-mascot"
          priority
          unoptimized
          aria-hidden
        />
      </div>

      <p className="welcome-eyebrow">Knowledge Library</p>
      <h1 id="welcome-headline" className="welcome-headline">
        All your documents.
        <span className="welcome-headline-accent">One library.</span>
      </h1>
      <p className="welcome-subhead">Organize • Connect • Understand</p>
      <p className="welcome-desc">
        Bring company knowledge into one organized library, structured by Space and ready to search,
        explore, and ask with citations.
      </p>

      {error ? (
        <p className="welcome-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="welcome-actions">
        <GoogleSignInButton href={googleLoginHref(nextPath)} disabled={!googleConfigured} />
        {!googleConfigured && !error ? (
          <p className="welcome-config-hint">Google sign-in is not available right now.</p>
        ) : null}
      </div>

      <SourcePills />
      <SecurityNote />
    </section>
  );
}
