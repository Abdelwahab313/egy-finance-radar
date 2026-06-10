/** @type {import('next').NextConfig} */

// In Docker the frontend is the only externally-exposed service (port 5040).
// Browser requests go to "/api/*" (relative — NEXT_PUBLIC_API_BASE is "") and
// Next proxies them server-side to the backend container over the internal
// Docker network.
//
// NOTE: Next evaluates rewrites() at BUILD time and bakes them into
// routes-manifest.json — `next start` does not re-run this. So BACKEND_ORIGIN
// must be present during `next build` (the Dockerfile sets it as a build ARG).
// Default targets the compose service name. Harmless in local `npm run dev`:
// there NEXT_PUBLIC_API_BASE defaults to an absolute http://localhost:8000, so
// nothing ever requests the relative "/api/*" that this rewrite handles.
const backend = process.env.BACKEND_ORIGIN || "http://backend:8000";

const nextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
