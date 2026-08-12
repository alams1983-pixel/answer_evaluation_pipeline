"use client";

import { useState } from 'react';
import { AdditionalPdf, uploadAdditionalPdf } from '@/lib/api';

interface AdditionalPdfUploaderProps {
  examId: string;
  onUploadComplete: (pdf: AdditionalPdf) => void;
}

export default function AdditionalPdfUploader({
  examId,
  onUploadComplete,
}: AdditionalPdfUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [label, setLabel] = useState('');
  const [pdfType, setPdfType] = useState<'instructions' | 'answer_key' | 'reference'>('reference');
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!label.trim()) {
      setError('Please enter a label for the PDF');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const result = await uploadAdditionalPdf(examId, file, label.trim(), pdfType);
      onUploadComplete(result);
      setLabel('');
      setPdfType('reference');
      if (e.target) e.target.value = '';
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="panel" style={{ padding: '1rem' }}>
      <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>Upload Additional PDF</h3>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>×</button>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label className="label">Label</label>
            <input
              type="text"
              className="input-field"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g., General Instructions, Model Answers"
              style={{ width: '100%' }}
            />
          </div>

          <div style={{ width: '160px' }}>
            <label className="label">Type</label>
            <select
              className="input-field"
              value={pdfType}
              onChange={(e) => setPdfType(e.target.value as 'instructions' | 'answer_key' | 'reference')}
              style={{ width: '100%' }}
            >
              <option value="instructions">Instructions</option>
              <option value="answer_key">Answer Key</option>
              <option value="reference">Reference</option>
            </select>
          </div>

          <div>
            <label className="btn btn-primary" style={{ cursor: uploading ? 'not-allowed' : 'pointer', opacity: uploading ? 0.6 : 1 }}>
              {uploading ? 'Uploading...' : 'Upload PDF'}
              <input
                type="file"
                accept=".pdf"
                onChange={handleUpload}
                disabled={uploading || !label.trim()}
                style={{ display: 'none' }}
              />
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
