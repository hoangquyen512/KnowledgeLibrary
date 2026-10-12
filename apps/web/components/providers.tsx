"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";
import { Toaster } from "sonner";
import { NavigationProgressProvider } from "@/components/navigation-progress";
import { UrlMask } from "@/components/url-mask";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
      }),
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <QueryClientProvider client={queryClient}>
        <NavigationProgressProvider>
          <UrlMask />
          {children}
          <Toaster richColors position="top-right" />
        </NavigationProgressProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
