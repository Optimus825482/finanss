/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== "production";
// Dev: local uvicorn (localhost:8012). Prod (Docker compose): backend servisi (backend:8012).
// BACKEND_HOST/BACKEND_PORT env ile her zaman override edilebilir.
const BACKEND_HOST = process.env.BACKEND_HOST || (isDev ? "localhost" : "backend");
const BACKEND_PORT = process.env.BACKEND_PORT || "8012";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        // Host/port env'den gelir (BACKEND_HOST/BACKEND_PORT); default 8012.
        // Docker compose'ta BACKEND_HOST=backend BACKEND_PORT=8012 verilir.
        destination: `http://${BACKEND_HOST}:${BACKEND_PORT}/api/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
