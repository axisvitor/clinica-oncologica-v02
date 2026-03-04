import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import { Analytics } from '@vercel/analytics/next'
import { Toaster } from '@/components/ui/toaster'
import { ErrorBoundary } from '@/components/error/ErrorBoundary'
import { ThemeProvider } from '@/components/theme-provider'
import './globals.css'

export const metadata: Metadata = {
  title: 'Hormonia - Quiz Mensal de Bem-Estar',
  description: 'Questionário mensal de bem-estar para pacientes',
  generator: 'v0.app',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className={`font-sans ${GeistSans.variable} ${GeistMono.variable}`}>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
          <ErrorBoundary>
            {children}
            <Toaster />
            {process.env.NEXT_PUBLIC_ENABLE_VERCEL_ANALYTICS === 'true' && <Analytics />}
          </ErrorBoundary>
        </ThemeProvider>
      </body>
    </html>
  )
}
