"use client";

import { useState, useRef, useCallback, useEffect } from 'react';
import { uploadFile, getSheetsForExam, deleteAllPendingSheets, deleteUploadBatch } from '@/lib/api';
import { useUploadBatchPolling } from '@/lib/use-upload-batch';

interface UploadStepProps {
  examId: string;
  onUploadComplete: () => void;
  onNavigateToMapping: () => void;
}

export default function UploadStep({ examId, onUploadComplete, onNavigateToMapping }: UploadStepProps) {
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [removing, setRemoving] = useState(false);
  const [deletingBatchId, setDeletingBatchId] = useState<string | null>(null);
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
        setError('Please upload a ZIP file containing PDFs');
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

  const handleRemoveAllPending = async () => {
    if (!confirm(`Remove all ${pendingCount} unmapped sheets? This will delete the PDFs and page images permanently.`)) return;
    setRemoving(true);
    try {
      await deleteAllPendingSheets(examId);
      setPendingCount(0);
      refetch();
      onUploadComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove pending sheets');
    } finally {
      setRemoving(false);
    }
  };

  const handleDeleteBatch = async (batchId: string) => {
    if (!confirm('Delete this upload batch and all associated sheets, PDFs, and page images?')) return;
    setDeletingBatchId(batchId);
    try {
      await deleteUploadBatch(examId, batchId);
      refetch();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete batch');
    } finally {
      setDeletingBatchId(null);
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
      onUploadComplete();
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

  const getProgressPercent = (batch: { total_pdfs: number; processed_pdfs: number }) => {
    if (batch.total_pdfs === 0) return 0;
    return Math.round((batch.processed_pdfs / batch.total_pdfs) * 100);
  };

  const hasReadyBatch = batches.some((b) => b.status === 'ready_for_mapping');
  const canMap = hasReadyBatch || pendingCount > 0;

  return (
    <div>
      <div className="section-header">
        <h2 className="text-md" style={{ margin: 0, fontWeight: 600 }}>Upload Answer Sheets</h2>
        <span className="section-badge">ZIP</span>
      </div>

      <div className="upload-drop-zone" style={{ marginBottom: '1rem' }}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          id="zip-file-input"
        />
        <label htmlFor="zip-file-input" style={{ cursor: 'pointer', display: 'block', padding: '1rem' }}>
          <svg style={{ width: '48px', height: '48px', margin: '0 auto 0.5rem', display: 'block', color: 'var(--text-muted)' }} xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          <div style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
            Drag & drop a ZIP file here, or click to select
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginBottom: '0.75rem' }}>
            ZIP should contain PDFs named like: <code style={{ color: 'var(--accent-primary)' }}>studentName_rollNo_class_section.pdf</code>
          </div>
          {selectedFile && (
            <div style={{ color: 'var(--accent-primary)', fontWeight: 600, marginTop: '0.5rem' }}>
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

      {error && (
        <div className="error-message" style={{ marginTop: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      {activeBatch && (
        <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 className="text-sm" style={{ margin: 0, fontWeight: 600 }}>Processing: {activeBatch.zip_filename}</h3>
            {getStatusBadge(activeBatch.status)}
          </div>

          <div className="progress-bar" style={{ marginBottom: '0.5rem' }}>
            <div className="progress-bar-fill" style={{ width: `${getProgressPercent(activeBatch)}%` }} />
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            {activeBatch.processed_pdfs} / {activeBatch.total_pdfs} PDFs processed
          </div>
        </div>
      )}

      {canMap && (
        <div style={{ textAlign: 'center', marginTop: '1.5rem', display: 'flex', gap: '1rem', justifyContent: 'center', alignItems: 'center' }}>
          <button className="btn btn-primary" style={{ fontSize: '1rem', padding: '0.75rem 2rem' }} onClick={onNavigateToMapping}>
            {pendingCount > 0 ? `Start One-by-One Mapping (${pendingCount} pending)` : 'Start Mapping'}
          </button>
          <button className="btn btn-secondary" style={{ fontSize: '0.875rem', padding: '0.75rem 1.5rem', color: 'var(--error)', border: '1px solid var(--error)' }} onClick={handleRemoveAllPending} disabled={removing}>
            {removing ? 'Removing...' : `Remove All Pending (${pendingCount})`}
          </button>
        </div>
      )}

      {!batchesLoading && batches.length > 0 && (
        <div className="panel" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
          <h3 className="text-sm" style={{ marginBottom: '1rem', fontWeight: 600 }}>Recent Uploads</h3>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>PDFs</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {batches.slice(0, 5).map((batch) => (
                  <tr key={batch.id}>
                    <td style={{ fontFamily: 'monospace' }}>{batch.zip_filename}</td>
                    <td>
                      {batch.total_pdfs > 0 ? `${batch.processed_pdfs}/${batch.total_pdfs}` : '-'}
                    </td>
                    <td>{getStatusBadge(batch.status)}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>
                      {new Date(batch.created_at).toLocaleString()}
                    </td>
                    <td>
                      <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDeleteBatch(batch.id)} disabled={deletingBatchId === batch.id}>
                        {deletingBatchId === batch.id ? 'Deleting...' : 'Delete'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
