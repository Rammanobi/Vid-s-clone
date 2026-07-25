import type { Metadata } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import "./globals.css"
import { ThemeProvider } from "@/components/layout/theme-provider"
import { DashboardLayout } from "@/components/layout/dashboard-layout"
import { AuthProvider } from "@/lib/auth-context"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"

export const metadata: Metadata = {
  title: {
    default: "Vid's Clone — Content Strategy Intelligence",
    template: "%s | Vid's Clone",
  },
  description:
    "AI-powered content strategy platform for Instagram Reels. Analyze performance, discover trends, and optimize your content with intelligent insights.",
  keywords: [
    "Instagram Reels",
    "content strategy",
    "social media analytics",
    "AI analytics",
    "creator tools",
    "video performance",
  ],
  authors: [{ name: "Vid's Clone" }],
  openGraph: {
    title: "Vid's Clone — Content Strategy Intelligence",
    description:
      "AI-powered content strategy platform for Instagram Reels. Analyze, discover, and optimize.",
    url: baseUrl,
    siteName: "Vid's Clone",
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Vid's Clone — Content Strategy Intelligence",
    description:
      "AI-powered content strategy platform for Instagram Reels. Analyze, discover, and optimize.",
  },
  robots: {
    index: true,
    follow: true,
  },
  metadataBase: new URL(baseUrl),
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable}`}
    >
      <head>
        <link rel="sitemap" type="application/xml" href="/sitemap.xml" />
      </head>
      <body className="min-h-screen bg-background font-sans antialiased scrollbar-thin">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            <DashboardLayout>{children}</DashboardLayout>
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
