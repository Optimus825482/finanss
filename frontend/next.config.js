/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== "production";
const BACKEND_HOST = process.env.BACKEND_HOST || "localhost";
const BACKEND_PORT = process.env.BACKEND_PORT || "8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // Host/port env'den gelir (BACKEND_HOST/BACKEND_PORT); default localhost:8000.
        // Docker compose'ta BACKEND_HOST=backend BACKEND_PORT=8012 verilir.
        destination: `http://${BACKEND_HOST}:${BACKEND_PORT}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
