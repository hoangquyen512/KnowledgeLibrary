"""Optional local seed helpers.

Super Admin is seeded via SEED_SUPER_ADMIN_EMAIL on first Google login — do not
hardcode production emails here.
"""

from __future__ import annotations


def main() -> None:
    print(
        "No static seed users. Set SEED_SUPER_ADMIN_EMAIL in .env, then sign in with Google."
    )


if __name__ == "__main__":
    main()
