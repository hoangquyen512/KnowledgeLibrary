"use client";

import { createContext, useContext } from "react";
import type { MeResponse } from "@/lib/api";

const AppUserContext = createContext<MeResponse | null>(null);

export function AppUserProvider({
  user,
  children,
}: {
  user: MeResponse;
  children: React.ReactNode;
}) {
  return <AppUserContext.Provider value={user}>{children}</AppUserContext.Provider>;
}

export function useAppUser(): MeResponse {
  const user = useContext(AppUserContext);
  if (!user) {
    throw new Error("useAppUser must be used within AppUserProvider");
  }
  return user;
}
