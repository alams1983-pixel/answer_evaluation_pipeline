"use client";

import { useState, useEffect } from 'react';

interface AuthImageProps {
  src: string;
  alt: string;
  className?: string;
  onClick?: () => void;
  loading?: 'lazy' | 'eager';
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const cache = new Map<string, string>();

export default function AuthImage({ src, alt, className, onClick, loading }: AuthImageProps) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const fetchImage = async () => {
      // Use the Next.js proxy path — build the real backend URL from it
      let url = src;
      if (src.startsWith('/api/files/')) {
        url = `${API_BASE}${src.replace('/api/files/', '/files/')}`;
      }

      if (cache.has(url)) {
        setBlobUrl(cache.get(url)!);
        return;
      }

      const token = localStorage.getItem('auth_token');
      if (!token) {
        setError(true);
        return;
      }

      try {
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          console.error(`AuthImage: failed to load ${url}, status ${res.status}`);
          setError(true);
          return;
        }

        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        cache.set(url, blobUrl);

        if (!cancelled) {
          setBlobUrl(blobUrl);
        }
      } catch (err) {
        console.error('AuthImage: network error:', err);
        setError(true);
      }
    };

    fetchImage();

    return () => {
      cancelled = true;
    };
  }, [src]);

  if (error) {
    return (
      <div className={className} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface2)', color: 'var(--muted)', fontSize: '0.75rem' }}>
        Image unavailable
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className={className} style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface2)' }}>
        <div style={{ width: 20, height: 20, border: '2px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
      </div>
    );
  }

  return (
    <img
      src={blobUrl}
      alt={alt}
      className={className}
      onClick={onClick}
      loading={loading}
    />
  );
}
