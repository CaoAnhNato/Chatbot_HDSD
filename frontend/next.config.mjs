/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
        port: '8000',
        pathname: '/static/**',
      },
      {
        protocol: 'https',
        hostname: 'chatbothdsd-production.up.railway.app',
        pathname: '/static/**',
      },
    ],
  },
  eslint: {
    // Ngăn chặn prompt tương tác của ESLint làm gián đoạn CI/CD build trên Vercel
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
