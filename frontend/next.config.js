/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== "production";
const BACKEND_HOST = isDev ? "localhost" : "backend";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // local dev → localhost:8012; Docker → backend:8012 (compose network)
        // Server-side rewrites only — browser calls use NEXT_PUBLIC_API_URL directly.
        destination: `http://${BACKEND_HOST}:8012/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
