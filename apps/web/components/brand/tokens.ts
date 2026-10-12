export const BRAND = {
  name: "Knowledge Library",
  tagline: "Explore • Understand • Grow",
  colors: {
    navy: "#102A6A",
    blue: "#2F5BEA",
    indigo: "#4B4FE8",
    violet: "#6C3EF0",
    softLavender: "#D9D5FF",
    background: "#F8FAFF",
  },
  paths: {
    logoFullLight: "/brand/logo/logo-full-light.svg",
    logoFullDark: "/brand/logo/logo-full-dark.svg",
    logoMark: "/brand/logo/logo-mark.png",
    logoMarkDark: "/brand/logo/logo-mark-dark.png",
    antFull: "/brand/mascot/knowledge-library-full-mascot.svg",
    antMark: "/brand/mascot/ant-mark.png",
    antSearch: "/brand/mascot/knowledge-library-full-mascot.svg",
    antEmpty: "/brand/mascot/knowledge-library-full-mascot.svg",
    antLoading: "/brand/mascot/ant-loading.png",
    appIcon: "/brand/app-icons/icon-512.png",
    sourceSvg: "/brand/mascot/knowledge-library-full-mascot.svg",
    sourcePng: "/brand/mascot/ant-full.png",
    appIcon192: "/brand/app-icons/icon-192.png",
    appIcon512: "/brand/app-icons/icon-512.png",
    favicon16: "/brand/favicon/favicon-16x16.png",
    favicon32: "/brand/favicon/favicon-32x32.png",
    faviconIco: "/brand/favicon/favicon.ico",
    ogImage: "/brand/social/og-image.png",
  },
} as const;

export type MascotMood = "full" | "search" | "empty" | "loading" | "mark";
