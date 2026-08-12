"use client";

import { getPageImageUrl } from '@/lib/api';
import AuthImage from './AuthImage';

interface PageThumbnailProps {
  sheetId: string;
  pageNo: number;
  onZoom: () => void;
  onDelete?: () => void;
}

export default function PageThumbnail({ sheetId, pageNo, onZoom, onDelete }: PageThumbnailProps) {
  return (
    <div className="page-thumb" title="Click to zoom">
      <AuthImage
        src={getPageImageUrl(sheetId, pageNo)}
        alt={`Page ${pageNo}`}
        onClick={onZoom}
        loading="lazy"
      />
      {onDelete && (
        <button
          className="page-thumb-remove"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          title="Remove page"
        >
          ✕
        </button>
      )}
      <div className="page-thumb-label">Page {pageNo}</div>
    </div>
  );
}
