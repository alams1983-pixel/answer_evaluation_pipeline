"use client";

import { useState, useEffect } from 'react';

interface ZoomModalProps {
  src: string;
  onClose: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function ZoomModal({ src, onClose }: ZoomModalProps) {
  const [imageSrc, setImageSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchImage = async () => {
      // Convert proxy path to backend URL
      let url = src;
      if (src.startsWith('/api/files/')) {
        url = `${API_BASE}${src.replace('/api/files/', '/files/')}`;
      }

      const token = localStorage.getItem('auth_token');
      if (!token) return;

      try {
        const res = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) return;

        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        if (!cancelled) setImageSrc(blobUrl);
      } catch (err) {
        console.error('ZoomModal: fetch failed:', err);
      }
    };

    fetchImage();
    return () => {
      cancelled = true;
    };
  }, [src]);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <div className="zoom-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <button className="zoom-modal-close" onClick={onClose} aria-label="Close zoom">✕</button>
      {imageSrc ? (
        <img src={imageSrc} alt="Zoomed page" />
      ) : (
        <div style={{ color: 'white', fontSize: '1.2rem' }}>Loading...</div>
      )}
    </div>
  );
}
