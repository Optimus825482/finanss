/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
      source: "/api/:path*",
      // Use internal Docker hostname — NEXT_PUBLIC_API_URL is the public URL
      // which would cause a loop if used here. Only fires when browser sends
      // relative /api/* requests (i.e. when NEXT_PUBLIC_API_URL is empty in build).
      destination: "http://backend:8012/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
