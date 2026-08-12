import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth';
import { LayoutProvider } from '@/components/LayoutContext';
import Header from '@/components/Header';
import Sidebar from '@/components/Sidebar';
import MainContent from '@/components/MainContent';

export const metadata: Metadata = {
  title: 'AI PDF Processing System',
  description: 'Answer sheet management and AI grading system',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <AuthProvider>
          <LayoutProvider>
            <Header />
            <Sidebar />
            <MainContent>{children}</MainContent>
          </LayoutProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
