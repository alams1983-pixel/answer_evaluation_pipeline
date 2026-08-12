'use client';

import Footer from '@/components/Footer';

export default function MainContent({ children }: { children: React.ReactNode }) {
  return (
    <div className="main-content">
      <div className="main-content-inner">
        {children}
      </div>
      <Footer />
    </div>
  );
}
