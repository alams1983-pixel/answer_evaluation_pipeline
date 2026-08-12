"use client";

import { useState, useRef, useCallback, useEffect } from 'react';

interface CropRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface CropOverlayProps {
  canvasRef: React.RefObject<HTMLCanvasElement | null>;
  pageWidth: number;
  pageHeight: number;
  onCropComplete: (crop: CropRect, previewDataUrl: string) => void;
  disabled?: boolean;
}

export default function CropOverlay({
  canvasRef,
  pageWidth,
  pageHeight,
  onCropComplete,
  disabled = false,
}: CropOverlayProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const currentRectRef = useRef<CropRect | null>(null);
  const [isSelecting, setIsSelecting] = useState(false);
  const [startPos, setStartPos] = useState<{ x: number; y: number } | null>(null);
  const [currentRect, setCurrentRect] = useState<CropRect | null>(null);

  const getCanvasCoords = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const overlay = overlayRef.current;
    if (!overlay) return { x: 0, y: 0 };

    const rect = overlay.getBoundingClientRect();
    const scaleX = pageWidth / rect.width;
    const scaleY = pageHeight / rect.height;

    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  }, [pageWidth, pageHeight]);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (disabled) return;
    const coords = getCanvasCoords(e);
    setIsSelecting(true);
    setStartPos(coords);
    const rect = { x: coords.x, y: coords.y, width: 0, height: 0 };
    setCurrentRect(rect);
    currentRectRef.current = rect;
  }, [disabled, getCanvasCoords]);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isSelecting || !startPos) return;

    const coords = getCanvasCoords(e);
    const x = Math.min(startPos.x, coords.x);
    const y = Math.min(startPos.y, coords.y);
    const width = Math.abs(coords.x - startPos.x);
    const height = Math.abs(coords.y - startPos.y);

    const rect = { x, y, width, height };
    setCurrentRect(rect);
    currentRectRef.current = rect;
  }, [isSelecting, startPos, getCanvasCoords]);

  const handleMouseUp = useCallback(() => {
    const rect = currentRectRef.current;

    if (!isSelecting || !rect) {
      setIsSelecting(false);
      setStartPos(null);
      return;
    }

    setIsSelecting(false);

    if (rect.width < 10 || rect.height < 10) {
      setCurrentRect(null);
      currentRectRef.current = null;
      setStartPos(null);
      return;
    }

    const canvas = canvasRef.current;
    if (canvas) {
      const canvasX = Math.round(rect.x);
      const canvasY = Math.round(rect.y);
      const canvasWidth = Math.round(rect.width);
      const canvasHeight = Math.round(rect.height);

      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = canvasWidth;
      tempCanvas.height = canvasHeight;
      const ctx = tempCanvas.getContext('2d');
      if (ctx) {
        ctx.drawImage(canvas, canvasX, canvasY, canvasWidth, canvasHeight, 0, 0, canvasWidth, canvasHeight);
        const dataUrl = tempCanvas.toDataURL('image/png');
        onCropComplete(rect, dataUrl);
      }
    }

    // Clear selection state — parent handles preview/attach UI
    setCurrentRect(null);
    setStartPos(null);
  }, [isSelecting, canvasRef, onCropComplete]);

  const handleDismiss = useCallback(() => {
    setCurrentRect(null);
    currentRectRef.current = null;
    setStartPos(null);
  }, []);

  useEffect(() => {
    if (disabled) {
      handleDismiss();
    }
  }, [disabled, handleDismiss]);

  const overlayStyle: React.CSSProperties = {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    cursor: disabled ? 'default' : 'crosshair',
    zIndex: 10,
  };

  const selectionStyle: React.CSSProperties = currentRect
    ? {
        position: 'absolute',
        left: `${(currentRect.x / pageWidth) * 100}%`,
        top: `${(currentRect.y / pageHeight) * 100}%`,
        width: `${(currentRect.width / pageWidth) * 100}%`,
        height: `${(currentRect.height / pageHeight) * 100}%`,
        border: '2px dashed var(--accent)',
        background: 'rgba(79, 142, 247, 0.15)',
        pointerEvents: 'none',
      }
    : {};

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
      <div
        ref={overlayRef}
        style={overlayStyle}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          if (isSelecting) handleMouseUp();
        }}
      >
        {currentRect && <div style={selectionStyle} />}
      </div>
    </div>
  );
}
