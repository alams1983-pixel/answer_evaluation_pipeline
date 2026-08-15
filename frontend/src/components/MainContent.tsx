'use client';

import Footer from '@/components/Footer';
import { useAuth } from '@/lib/auth';

export default function MainContent({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  return (
    <div className={`main-content ${!user ? 'no-sidebar' : ''}`}>
      <div className={`main-content-inner ${!user ? 'public-inner' : ''}`}>
        {children}
      </div>
      <Footer />
    </div>
  );
}
