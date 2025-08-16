/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
  // Enable standalone output for Docker
  output: 'standalone',
  // Disable image optimization for Docker (optional)
  images: {
    unoptimized: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  }
};

export default nextConfig;
