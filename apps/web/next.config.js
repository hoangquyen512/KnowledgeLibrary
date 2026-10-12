/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ["recharts"],
  async redirects() {
    return [
      { source: "/app/admin", destination: "/app/settings/admin", permanent: false },
      { source: "/app/admin/:path*", destination: "/app/settings/admin/:path*", permanent: false },
      { source: "/app/trash", destination: "/app/settings/trash", permanent: false },
    ];
  },
  async rewrites() {
    const api =
      process.env.API_INTERNAL_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${api.replace(/\/$/, "")}/api/v1/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
