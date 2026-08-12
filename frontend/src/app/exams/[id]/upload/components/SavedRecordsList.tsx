"use client";

import { useState } from 'react';
import PageThumbnail from './PageThumbnail';
import ZoomModal from './ZoomModal';
import AuthImage from './AuthImage';
import { AnswerSheet, getPageImageUrl } from '@/lib/api';

interface SavedRecordsListProps {
  sheets: AnswerSheet[];
  onEdit: (sheet: AnswerSheet) => void;
  onDelete: (sheetId: string) => void;
}

export default function SavedRecordsList({ sheets, onEdit, onDelete }: SavedRecordsListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [zoomSrc, setZoomSrc] = useState<string | null>(null);

  if (sheets.length === 0) return null;

  return (
    <div className="saved-records">
      <h3 style={{ marginBottom: '0.75rem', fontSize: '0.95rem' }}>
        Saved Records ({sheets.length})
      </h3>

      {sheets.map((sheet) => {
        const isExpanded = expandedId === sheet.id;
        return (
          <div key={`saved-${sheet.id}`} className="saved-record-item">
            <div
              className="saved-record-header"
              onClick={() => setExpandedId(isExpanded ? null : sheet.id)}
            >
              <div className="saved-record-meta">
                <span>{sheet.student_name || '(no name)'}</span>
                <span style={{ color: 'var(--muted)', fontWeight: 400 }}>
                  Roll: {sheet.roll_no || '-'}
                </span>
                <span style={{ color: 'var(--muted)', fontWeight: 400 }}>
                  Class: {sheet.class_label || '-'}
                </span>
                <span className={`status-badge s-${sheet.status}`}>{sheet.status}</span>
              </div>
              <div className="saved-record-actions">
                <button
                  className="btn btn-secondary"
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    onEdit(sheet);
                  }}
                >
                  Edit
                </button>
                <button
                  className="btn"
                  style={{ padding: '0.25rem 0.75rem', fontSize: '0.8rem', color: 'var(--red)' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete record for "${sheet.student_name || 'unnamed'}"?`)) {
                      onDelete(sheet.id);
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
            {isExpanded && (
              <div className="saved-record-body expanded">
                <div className="page-thumbnails">
                  {Array.from({ length: sheet.page_count }, (_, i) => i + 1).map((pn) => (
                    <PageThumbnail
                      key={pn}
                      sheetId={sheet.id}
                      pageNo={pn}
                      onZoom={() => setZoomSrc(getPageImageUrl(sheet.id, pn))}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {zoomSrc && <ZoomModal src={zoomSrc} onClose={() => setZoomSrc(null)} />}
    </div>
  );
}
