"use client";

import { useState, useEffect, useRef } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, getBatchesForExam, createBatch, getBatch, downloadBatchJsonl, deleteBatchItem, updateBatch, uploadFilesForBatch, submitToGemini, downloadFinalJsonl, cancelBatch, refreshBatch, deleteBatch, getBatchUploadStatus, BatchJob, BatchDetail, BatchItem, AnswerSheet, UploadStatus } from '@/lib/api';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';

interface Exam {
  id: string;
  title: string;
  status: string;
  complexity_tier: string;
}

export default function BatchesPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const router = useRouter();
  const examId = params.id as string;

  const [exam, setExam] = useState<Exam | null>(null);
  const [batches, setBatches] = useState<BatchJob[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [provider, setProvider] = useState('gemini');
  const [model, setModel] = useState('');
  const [deletingItem, setDeletingItem] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadStatus['upload_progress']>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<string | null>(null);
  const [deletingBatch, setDeletingBatch] = useState<string | null>(null);
  const [viewingError, setViewingError] = useState<{ error: string; raw_response: any } | null>(null);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role!)) {
      loadData();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role!))) {
      setLoading(false);
    }
  }, [examId, user, authLoading]);

  useEffect(() => {
    if (exam?.complexity_tier) {
      const modelMap: Record<string, string> = {
        simple: 'gemini-2.0-flash',
        standard: 'gemini-2.5-flash',
        complex: 'gemini-2.5-pro',
      };
      setModel(modelMap[exam.complexity_tier] || 'gemini-2.5-flash');
    }
  }, [exam]);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [examData, batchesData] = await Promise.all([
        apiGet<Exam>(`/exams/${examId}/`),
        getBatchesForExam(examId),
      ]);
      setExam(examData);
      setBatches(batchesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadBatchDetail = async (batchId: string) => {
    try {
      const detail = await getBatch(batchId);
      setSelectedBatch(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load batch details');
    }
  };

  const handleCreateBatch = async () => {
    try {
      setCreating(true);
      await createBatch(examId, { provider, model });
      setError(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create batch');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteItem = async (batchId: string, itemId: string) => {
    try {
      setDeletingItem(itemId);
      await deleteBatchItem(batchId, itemId);
      setError(null);
      await loadBatchDetail(batchId);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove item');
    } finally {
      setDeletingItem(null);
    }
  };

  const handleUpdateBatchModel = async (batchId: string, newProvider: string, newModel: string) => {
    try {
      await updateBatch(batchId, { provider: newProvider, model: newModel });
      setError(null);
      await loadData();
      if (selectedBatch && selectedBatch.id === batchId) {
        await loadBatchDetail(batchId);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update batch');
    }
  };

  const handleDownloadJsonl = async (batchId: string) => {
    try {
      setDownloading(batchId);
      await downloadBatchJsonl(batchId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download JSONL');
    } finally {
      setDownloading(null);
    }
  };

  const handleUploadFiles = async (batchId: string) => {
    try {
      setSubmitting(batchId);
      setUploadProgress({ phase: 'starting', current: 0, total: 0, message: 'Starting file upload...' });

      await uploadFilesForBatch(batchId);

      pollIntervalRef.current = setInterval(async () => {
        try {
          const status = await getBatchUploadStatus(batchId);
          setUploadProgress(status.upload_progress);

          if (status.status === 'files_uploaded') {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setUploadProgress(null);
            setSubmitting(null);
            await loadData();
            await loadBatchDetail(batchId);
            return;
          }

          if (status.status !== 'uploading' && !status.upload_progress) {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setUploadProgress(null);
            setSubmitting(null);
            if (status.status === 'submitted' || status.status === 'in_progress') {
              setError(null);
            }
            await loadData();
            await loadBatchDetail(batchId);
          }

          if (status.status === 'failed') {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setUploadProgress(null);
            setSubmitting(null);
            const errorMsg = status.upload_progress?.message || 'Failed to upload files';
            setError(errorMsg.replace('Upload failed: ', ''));
            await loadData();
          }
        } catch (err) {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setUploadProgress(null);
          setSubmitting(null);
          setError(err instanceof Error ? err.message : 'Failed to check upload status');
        }
      }, 1000);

    } catch (err) {
      setSubmitting(null);
      setUploadProgress(null);
      setError(err instanceof Error ? err.message : 'Failed to upload files');
    }
  };

  const handleSubmitToGemini = async (batchId: string) => {
    try {
      setSubmitting(batchId);
      setError(null);
      await submitToGemini(batchId);
      setError(null);
      await loadData();
      await loadBatchDetail(batchId);
    } catch (err) {
      setSubmitting(null);
      setError(err instanceof Error ? err.message : 'Failed to submit to Gemini');
      await loadData();
      await loadBatchDetail(batchId);
    }
  };

  const handleRetryUpload = async (batchId: string) => {
    setError(null);
    await handleUploadFiles(batchId);
  };

  const handleCancelBatch = async (batchId: string) => {
    try {
      setCancelling(batchId);
      await cancelBatch(batchId);
      setError(null);
      await loadData();
      await loadBatchDetail(batchId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel batch');
    } finally {
      setCancelling(null);
    }
  };

  const handleRefreshBatch = async (batchId: string) => {
    try {
      setRefreshing(batchId);
      const detail = await refreshBatch(batchId);
      setError(null);
      setSelectedBatch(detail);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh batch');
    } finally {
      setRefreshing(null);
    }
  };

  const handleDeleteBatch = async (batchId: string) => {
    if (!confirm('Are you sure you want to delete this batch?')) return;
    try {
      setDeletingBatch(batchId);
      await deleteBatch(batchId);
      setError(null);
      setSelectedBatch(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete batch');
    } finally {
      setDeletingBatch(null);
    }
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user || !['admin', 'teacher'].includes(user.role!)) {
    return <div>Access denied</div>;
  }

  if (!exam) {
    return <div>Exam not found</div>;
  }

  const getStatusBadge = (status: string) => {
    const colorMap: Record<string, string> = {
      draft: 'blue',
      uploading: 'yellow',
      files_uploaded: 'teal',
      review: 'purple',
      submitted: 'yellow',
      in_progress: 'yellow',
      completed: 'green',
      failed: 'red',
      cancelled: 'orange',
      expired: 'orange',
    };
    return (
      <span className={`node node-${colorMap[status] || 'blue'}`}>
        {status}
      </span>
    );
  };

  const getItemStatusBadge = (status: string) => {
    const colorMap: Record<string, string> = {
      pending: 'blue',
      completed: 'green',
      failed: 'red',
    };
    return (
      <span className={`node node-${colorMap[status] || 'blue'}`}>
        {status}
      </span>
    );
  };

  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <Link href={`/exams/${examId}`} className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
          &larr; Back to Exam
        </Link>
        <h1 className="text-xl" style={{ marginBottom: '0.25rem' }}>{exam.title} &mdash; Batches</h1>
        <p style={{ color: 'var(--text-muted)', margin: 0 }}>Manage JSONL batches for AI grading</p>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 className="text-lg" style={{ fontWeight: 600, marginBottom: '1rem' }}>Prepare JSONL Batch</h2>
        <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
          Build a JSONL file from all mapped answer sheets. You can review and download the file before submitting to AI.
        </p>

        {exam.complexity_tier && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Exam Complexity: </span>
            <span className={`node node-${exam.complexity_tier === 'simple' ? 'green' : exam.complexity_tier === 'complex' ? 'red' : 'blue'}`}>
              {exam.complexity_tier}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginLeft: '1rem' }}>Auto-selected model: </span>
            <code style={{ color: 'var(--accent-primary)', fontSize: '0.875rem' }}>{model || 'Loading...'}</code>
          </div>
        )}

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label className="form-label">Provider</label>
            <select
              className="form-input"
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                setModel(e.target.value === 'openai' ? 'gpt-4.1-mini' : model || 'gemini-2.5-flash');
              }}
            >
              <option value="gemini">Gemini</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <div>
            <label className="form-label">Model</label>
            <input
              type="text"
              className="form-input"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Auto-selected from complexity tier"
            />
          </div>
          <button
            className="btn btn-primary"
            onClick={handleCreateBatch}
            disabled={creating || !model}
          >
            {creating ? 'Creating...' : 'Prepare JSONL'}
          </button>
        </div>
      </div>

      <div className="panel" style={{ padding: '1.5rem' }}>
        <h2 className="text-lg" style={{ fontWeight: 600, marginBottom: '1rem' }}>Batch History</h2>

        {batches.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>No batches created yet.</p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Created</th>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Items</th>
                  <th>Progress</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {batches.map((batch) => (
                  <tr key={batch.id}>
                    <td style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                      {new Date(batch.created_at).toLocaleDateString()} {new Date(batch.created_at).toLocaleTimeString()}
                    </td>
                    <td>
                      <span className="node node-teal">{batch.provider}</span>
                    </td>
                    <td style={{ fontSize: '0.875rem' }}>{batch.model}</td>
                    <td>{batch.item_count}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ flex: 1, height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${batch.item_count > 0 ? (batch.completed_count / batch.item_count) * 100 : 0}%`,
                              height: '100%',
                              background: batch.status === 'failed' ? 'var(--error)' : 'var(--success)',
                              borderRadius: '3px',
                            }}
                          />
                        </div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {batch.completed_count}/{batch.item_count}
                        </span>
                      </div>
                    </td>
                    <td>
                      <span
                        style={batch.status === 'failed' && batch.poll_error ? { cursor: 'help' } : {}}
                        title={batch.status === 'failed' && batch.poll_error ? batch.poll_error : undefined}
                      >
                        {getStatusBadge(batch.status)}
                      </span>
                    </td>
                    <td style={{ display: 'flex', gap: '0.5rem' }}>
                      <button className="btn btn-secondary" onClick={() => loadBatchDetail(batch.id)}>
                        View
                      </button>
                      {batch.status === 'draft' && batch.input_file_path && (
                        <button className="btn btn-secondary" onClick={() => handleDownloadJsonl(batch.id)} disabled={downloading === batch.id}>
                          {downloading === batch.id ? 'Downloading...' : 'Download Draft JSONL'}
                        </button>
                      )}
                      {batch.status === 'files_uploaded' && (
                        <button className="btn btn-secondary" onClick={() => downloadFinalJsonl(batch.id)} disabled={downloading === batch.id}>
                          {downloading === batch.id ? 'Downloading...' : 'Download Final JSONL'}
                        </button>
                      )}
                      {['draft', 'cancelled', 'failed'].includes(batch.status) && (
                        <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDeleteBatch(batch.id)} disabled={deletingBatch === batch.id}>
                          {deletingBatch === batch.id ? 'Deleting...' : 'Delete'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selectedBatch && (
        <div className="modal-overlay" onClick={() => setSelectedBatch(null)}>
          <div className="modal-content" style={{ maxWidth: '900px', maxHeight: '80vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ marginBottom: 0 }}>Batch Details</h2>
              <button onClick={() => setSelectedBatch(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <label className="form-label">Status</label>
                <div style={{ padding: '0.5rem 0' }}>{getStatusBadge(selectedBatch.status)}</div>
              </div>
              <div>
                <label className="form-label">Items</label>
                <div style={{ padding: '0.5rem 0' }}>{selectedBatch.item_count}</div>
              </div>
              <div>
                <label className="form-label">Provider</label>
                <select
                  className="form-input"
                  value={selectedBatch.provider}
                  disabled={selectedBatch.status !== 'draft'}
                  onChange={(e) => {
                    const newProvider = e.target.value;
                    const newModel = newProvider === 'openai' ? 'gpt-4.1-mini' : 'gemini-2.5-flash';
                    handleUpdateBatchModel(selectedBatch.id, newProvider, newModel);
                  }}
                >
                  <option value="gemini">Gemini</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
              <div>
                <label className="form-label">Model</label>
                <input
                  type="text"
                  className="form-input"
                  value={selectedBatch.model}
                  disabled={selectedBatch.status !== 'draft'}
                  onChange={(e) => {
                    handleUpdateBatchModel(selectedBatch.id, selectedBatch.provider, e.target.value);
                  }}
                />
              </div>
              <div>
                <label className="form-label">Completed</label>
                <div style={{ padding: '0.5rem 0' }}>{selectedBatch.completed_count}</div>
              </div>
              <div>
                <label className="form-label">Failed</label>
                <div style={{ padding: '0.5rem 0', color: selectedBatch.failed_count > 0 ? 'var(--error)' : 'inherit' }}>{selectedBatch.failed_count}</div>
              </div>
              {selectedBatch.last_polled_at && (
                <div>
                  <label className="form-label">Last Polled</label>
                  <div style={{ padding: '0.5rem 0', fontSize: '0.875rem', color: 'var(--text-muted)' }}>
                    {new Date(selectedBatch.last_polled_at).toLocaleString()}
                  </div>
                </div>
              )}
              {selectedBatch.provider_batch_id && (
                <div>
                  <label className="form-label">Provider Batch ID</label>
                  <div style={{ padding: '0.5rem 0', fontSize: '0.875rem', fontFamily: 'monospace' }}>{selectedBatch.provider_batch_id}</div>
                </div>
              )}
            </div>

            {uploadProgress && submitting === selectedBatch.id && (
              <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem', borderLeft: '3px solid var(--accent-primary)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>
                      {uploadProgress.message}
                    </div>
                    {uploadProgress.total > 0 && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <div style={{ flex: 1, height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${(uploadProgress.current / uploadProgress.total) * 100}%`,
                              height: '100%',
                              background: 'var(--accent-primary)',
                              borderRadius: '3px',
                              transition: 'width 0.3s ease',
                            }}
                          />
                        </div>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {uploadProgress.current}/{uploadProgress.total}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="node node-yellow">
                    {uploadProgress.phase === 'ready' ? 'Ready' : 'Uploading'}
                  </div>
                </div>
              </div>
            )}

            {selectedBatch.status === 'failed' && selectedBatch.poll_error && (
              <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem', borderLeft: '3px solid var(--error)', background: 'var(--error-bg)' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                  <span className="node node-red">Failed</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.875rem', color: 'var(--error-text)', fontWeight: 600, marginBottom: '0.25rem' }}>
                      Batch submission failed
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {selectedBatch.poll_error}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
              {selectedBatch.status === 'draft' && selectedBatch.input_file_path && (
                <button className="btn btn-secondary" onClick={() => handleDownloadJsonl(selectedBatch.id)} disabled={downloading === selectedBatch.id}>
                  {downloading === selectedBatch.id ? 'Downloading...' : 'Download Draft JSONL'}
                </button>
              )}
              {selectedBatch.status === 'draft' && (
                <button className="btn btn-primary" onClick={() => handleUploadFiles(selectedBatch.id)} disabled={submitting === selectedBatch.id}>
                  {submitting === selectedBatch.id ? 'Uploading...' : 'Upload Files to Gemini'}
                </button>
              )}
              {selectedBatch.status === 'files_uploaded' && (
                <>
                  <button className="btn btn-secondary" onClick={() => downloadFinalJsonl(selectedBatch.id)} disabled={downloading === selectedBatch.id}>
                    {downloading === selectedBatch.id ? 'Downloading...' : 'Download Final JSONL'}
                  </button>
                  <button className="btn btn-primary" onClick={() => handleSubmitToGemini(selectedBatch.id)} disabled={submitting === selectedBatch.id}>
                    {submitting === selectedBatch.id ? 'Submitting...' : 'Submit to Gemini'}
                  </button>
                </>
              )}
              {(selectedBatch.status === 'submitted' || selectedBatch.status === 'in_progress') && (
                <>
                  <button className="btn btn-secondary" onClick={() => handleRefreshBatch(selectedBatch.id)} disabled={refreshing === selectedBatch.id}>
                    {refreshing === selectedBatch.id ? 'Refreshing...' : 'Refresh'}
                  </button>
                  <button className="btn btn-secondary" style={{ color: 'var(--error)' }} onClick={() => handleCancelBatch(selectedBatch.id)} disabled={cancelling === selectedBatch.id}>
                    {cancelling === selectedBatch.id ? 'Cancelling...' : 'Cancel'}
                  </button>
                </>
              )}
              {selectedBatch.status === 'completed' && (
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <span className="node node-green">All items processed</span>
                  <button className="btn btn-primary" onClick={async () => {
                    if (!confirm('Publish all reviewed gradings for this exam? Students will be able to see their results.')) return;
                    try {
                      setSubmitting(selectedBatch.id);
                      const result = await apiPost<{ published_count: number }>(`/exams/${examId}/publish-all`, {});
                      setError(null);
                      alert(`Published ${result.published_count} grading(s)`);
                      await loadData();
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Failed to publish gradings');
                    } finally {
                      setSubmitting(null);
                    }
                  }} disabled={submitting === selectedBatch.id}>
                    {submitting === selectedBatch.id ? 'Publishing...' : 'Publish All Results'}
                  </button>
                </div>
              )}
              {selectedBatch.status === 'failed' && (
                <button className="btn btn-primary" onClick={() => handleRetryUpload(selectedBatch.id)} disabled={submitting === selectedBatch.id}>
                  {submitting === selectedBatch.id ? 'Retrying...' : 'Retry Upload'}
                </button>
              )}
            </div>

            <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '1rem' }}>Items ({selectedBatch.items.length})</h3>
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Sheet ID</th>
                    <th>Preview</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedBatch.items.map((item: BatchItem) => (
                    <tr key={item.id}>
                      <td style={{ fontSize: '0.875rem', fontFamily: 'monospace' }}>
                        {item.sheet_id.slice(-8)}
                      </td>
                      <td style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                        {item.prompt_preview || '-'}
                      </td>

                      <td>{getItemStatusBadge(item.status)}</td>
                      <td>
                        {selectedBatch.status === 'draft' && item.status === 'pending' && (
                          <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDeleteItem(selectedBatch.id, item.id)} disabled={deletingItem === item.id}>
                            {deletingItem === item.id ? 'Removing...' : 'Remove'}
                          </button>
                        )}
                        {item.error && (
                          <button onClick={() => setViewingError({ error: item.error!, raw_response: (item as any).raw_response })} style={{ fontSize: '0.75rem', color: 'var(--error)', marginLeft: '0.5rem', background: 'none', border: '1px solid var(--error)', borderRadius: 'var(--radius-sm)', padding: '0.1rem 0.4rem', cursor: 'pointer' }} title="Click to view details">
                            Error
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {viewingError && (
        <div className="modal-overlay" onClick={() => setViewingError(null)}>
          <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '80vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ marginBottom: 0, color: 'var(--error-text)' }}>Error Details</h2>
              <button onClick={() => setViewingError(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
            </div>

            <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem', borderLeft: '3px solid var(--error)', background: 'var(--error-bg)' }}>
              <div style={{ fontSize: '0.875rem', color: 'var(--error-text)', fontWeight: 600, marginBottom: '0.5rem' }}>
                Error Message
              </div>
              <div style={{ fontSize: '0.8rem', fontFamily: 'monospace', wordBreak: 'break-word' }}>
                {viewingError.error}
              </div>
            </div>

            {viewingError.raw_response && (
              <div className="panel" style={{ padding: '1rem' }}>
                <div style={{ fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                  Raw Response from Gemini
                </div>
                <pre style={{
                  background: 'var(--bg-tertiary)',
                  padding: '1rem',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.75rem',
                  overflow: 'auto',
                  maxHeight: '400px',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-word',
                }}>
                  {JSON.stringify(viewingError.raw_response, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
