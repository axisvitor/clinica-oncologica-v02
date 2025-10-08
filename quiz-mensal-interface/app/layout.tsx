import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import { Analytics } from '@vercel/analytics/next'
import { Toaster } from '@/components/ui/toaster'
import { ErrorBoundary } from '@/components/error/ErrorBoundary'
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
    <html lang="pt-BR">
      <body className={`font-sans ${GeistSans.variable} ${GeistMono.variable}`}>
        <ErrorBoundary>
          {children}
          <Toaster />
          <Analytics />
        </ErrorBoundary>
      </body>
    </html>
  )
}