"use client";

import { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react';

interface PDFViewerCanvasProps {
  imageUrl: string;
  onImageReady?: (canvas: HTMLCanvasElement, pageWidth: number, pageHeight: number) => void;
  className?: string;
}

export interface PDFViewerCanvasRef {
  getCanvas: () => HTMLCanvasElement | null;
  getPageWidth: () => number;
  getPageHeight: () => number;
}

/**
 * Renders a pre-rasterized page image from the backend.
 * The backend already converts PDF pages to PNG during extraction,
 * so we just display the image with <img> instead of using pdf.js.
 * A hidden <canvas> draws the image so CropOverlay can extract pixel data for crops.
 */
const PDFViewerCanvas = forwardRef<PDFViewerCanvasRef, PDFViewerCanvasProps>(
  ({ imageUrl, onImageReady, className }, ref) => {
    const imgRef = useRef<HTMLImageElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const [pageWidth, setPageWidth] = useState(0);
    const [pageHeight, setPageHeight] = useState(0);

    useImperativeHandle(ref, () => ({
      getCanvas: () => canvasRef.current,
      getPageWidth: () => pageWidth,
      getPageHeight: () => pageHeight,
    }));

    const handleLoad = useCallback(() => {
      const img = imgRef.current;
      const canvas = canvasRef.current;
      if (!img || !canvas) return;

      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      setPageWidth(img.naturalWidth);
      setPageHeight(img.naturalHeight);

      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(img, 0, 0);
        onImageReady?.(canvas, img.naturalWidth, img.naturalHeight);
      }
    }, [onImageReady]);

    // Reset dimensions when URL changes
    useEffect(() => {
      setPageWidth(0);
      setPageHeight(0);
    }, [imageUrl]);

    return (
      <div style={{ position: 'relative' }}>
        {/* Visible image — no pdf.js needed, backend already rasterized to PNG */}
        <img
          ref={imgRef}
          src={imageUrl}
          alt="Question paper page"
          className={className}
          onLoad={handleLoad}
          crossOrigin="anonymous"
          style={{ display: 'block', maxWidth: '100%', height: 'auto' }}
        />

        {/* Hidden canvas — used by CropOverlay to extract cropped pixel data */}
        <canvas ref={canvasRef} style={{ display: 'none' }} />
      </div>
    );
  }
);

PDFViewerCanvas.displayName = 'PDFViewerCanvas';

export default PDFViewerCanvas;
