/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://backend:8012/api/:path*" },
    ];
  },
};

module.exports = nextConfig;
