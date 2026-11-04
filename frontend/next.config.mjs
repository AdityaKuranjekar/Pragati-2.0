/** @type {import('next').NextConfig} */
// NEXT_DIST lets a mock build and a real-server build live side by side (NEXT_PUBLIC_API_BASE is compiled in).
const nextConfig = { reactStrictMode: true, distDir: process.env.NEXT_DIST || ".next" };
export default nextConfig;
