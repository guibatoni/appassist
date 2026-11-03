import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  // Uma única exportação funciona no v0/Vercel e no WebView2 offline.
  // Não há Next.js server nem APIs hospedadas para as ISOs dos usuários.
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
}

export default nextConfig
