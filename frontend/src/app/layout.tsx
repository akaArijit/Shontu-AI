import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from '@/components/providers/QueryProvider';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'MFD Fund Monitoring Dashboard',
  description: 'Internal fund monitoring dashboard for Mutual Fund Distributors',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} font-sans antialiased`}>
      <body className="bg-neutral-50 text-neutral-900">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}