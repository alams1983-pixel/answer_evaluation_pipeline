"use client";

import { useState, useRef, useCallback, useEffect } from 'react';
import { uploadFile, getSheetsForExam } from '@/lib/api';
import { useUploadBatchPolling } from '@/lib/use-upload-batch';
import { useRouter } from 'next/navigation';

interface ZipUploadProps {
  examId: string;
  onUploadComplete?: () => void;
}

interface UploadBatch {
  id: string;
  exam_id: string;
  uploaded_by: string | null;
  zip_filename: string;
  total_pdfs: number;
  processed_pdfs: number;
  status: string;
  created_at: string;
}

export default function ZipUpload({ examId, onUploadComplete }: ZipUploadProps) {
  const router = useRouter();
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { batches, loading: batchesLoading, refetch } = useUploadBatchPolling(examId);

  const activeBatch = batches.find(
    (b) => b.status === 'extracting' || b.status === 'ready_for_mapping'
  );

  useEffect(() => {
    const loadPending = async () => {
      try {
        const pending = await getSheetsForExam(examId, 'pending_mapping');
        setPendingCount(pending.length);
      } catch (err) {
        console.error('Failed to load pending sheets:', err);
      }
    };
    loadPending();
    const interval = setInterval(loadPending, 5000);
    return () => clearInterval(interval);
  }, [examId]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        setSelectedFile(file);
        setError(null);
      } else {
        setError('Please upload a ZIP file');
      }
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        setSelectedFile(file);
        setError(null);
      } else {
        setError('Please upload a ZIP file');
      }
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      await uploadFile(`/exams/${examId}/sheets/upload-zip/`, formData);

      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      refetch();

      onUploadComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'extracting':
        return <span className="node node-yellow">Extracting...</span>;
      case 'ready_for_mapping':
        return <span className="node node-green">Ready for Mapping</span>;
      case 'completed':
        return <span className="node node-teal">Completed</span>;
      case 'failed':
        return <span className="node node-red">Failed</span>;
      default:
        return <span className="node node-blue">{status}</span>;
    }
  };

  const getProgressPercent = (batch: UploadBatch) => {
    if (batch.total_pdfs === 0) return 0;
    return Math.round((batch.processed_pdfs / batch.total_pdfs) * 100);
  };

  return (
    <div>
      <div className="section-header">
        <h2 style={{ margin: 0 }}>Upload Answer Sheets</h2>
        <span className="section-badge">ZIP</span>
      </div>

      {/* Upload Area */}
      <div
        className={`panel ${dragActive ? 'drag-active' : ''}`}
        style={{
          padding: '2rem',
          textAlign: 'center',
          border: dragActive ? '2px dashed var(--accent)' : '1px dashed var(--border)',
          marginBottom: '1.5rem',
          transition: 'all 0.2s',
        }}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          id="zip-file-input"
        />
        <label
          htmlFor="zip-file-input"
          style={{
            cursor: 'pointer',
            display: 'block',
            padding: '1rem',
          }}
        >
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📁</div>
          <div style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
            Drag & drop a ZIP file here, or click to select
          </div>
          {selectedFile && (
            <div style={{ color: 'var(--accent)', fontWeight: 600, marginTop: '0.5rem' }}>
              Selected: {selectedFile.name}
            </div>
          )}
        </label>
        <button
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          style={{ marginTop: '1rem' }}
        >
          {uploading ? 'Uploading...' : 'Upload ZIP'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button
            onClick={() => setError(null)}
            style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}
          >
            ×
          </button>
        </div>
      )}

      {/* Upload Progress */}
      {activeBatch && (
        <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0 }}>Processing: {activeBatch.zip_filename}</h3>
            {getStatusBadge(activeBatch.status)}
          </div>

          {/* Progress Bar */}
          <div
            style={{
              width: '100%',
              height: '8px',
              background: 'var(--surface2)',
              borderRadius: '4px',
              overflow: 'hidden',
              marginBottom: '0.5rem',
            }}
          >
            <div
              style={{
                width: `${getProgressPercent(activeBatch)}%`,
                height: '100%',
                background: 'linear-gradient(90deg, var(--accent), var(--accent2))',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            {activeBatch.processed_pdfs} / {activeBatch.total_pdfs} PDFs processed
          </div>
        </div>
      )}

      {(activeBatch?.status === 'ready_for_mapping' || pendingCount > 0) && (
        <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem', border: '2px solid var(--green)', textAlign: 'center' }}>
          <h3 style={{ color: 'var(--green)', marginBottom: '0.5rem' }}>✅ Ready to Map!</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
            {pendingCount > 0
              ? `${pendingCount} answer sheet(s) waiting. Review each one-by-one.`
              : `${activeBatch?.total_pdfs} answer sheet(s) extracted. Review each one-by-one.`}
          </p>
          <button
            className="btn btn-primary"
            style={{ fontSize: '1.05rem', padding: '0.75rem 2rem' }}
            onClick={() => router.push(`/exams/${examId}/upload`)}
          >
            Start One-by-One Mapping →
          </button>
        </div>
      )}

      {/* Recent Uploads */}
      {!batchesLoading && batches.length > 0 && (
        <div className="panel" style={{ padding: '1.5rem' }}>
          <h3 style={{ marginBottom: '1rem' }}>Recent Uploads</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '0.75rem', textAlign: 'left' }}>Filename</th>
                <th style={{ padding: '0.75rem', textAlign: 'left' }}>PDFs</th>
                <th style={{ padding: '0.75rem', textAlign: 'left' }}>Status</th>
                <th style={{ padding: '0.75rem', textAlign: 'left' }}>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {batches.slice(0, 5).map((batch) => (
                <tr key={batch.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.75rem' }}>{batch.zip_filename}</td>
                  <td style={{ padding: '0.75rem' }}>
                    {batch.total_pdfs > 0 ? `${batch.processed_pdfs}/${batch.total_pdfs}` : '-'}
                  </td>
                  <td style={{ padding: '0.75rem' }}>{getStatusBadge(batch.status)}</td>
                  <td style={{ padding: '0.75rem', color: 'var(--text-secondary)' }}>
                    {new Date(batch.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
