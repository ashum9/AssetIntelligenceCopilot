import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Asset Intelligence Copilot',
  description: 'AI-powered oilfield asset copilot with generative UI, runtime overrides, and two-level memory.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="h-full bg-slate-50 text-slate-900">
      <body className="h-full antialiased overflow-hidden selection:bg-sky-500 selection:text-white bg-slate-50 text-slate-900">
        {children}
      </body>
    </html>
  );
}
