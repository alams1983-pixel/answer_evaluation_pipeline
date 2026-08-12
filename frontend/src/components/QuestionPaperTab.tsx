"use client";

import { useState, useEffect, useCallback } from 'react';
import {
  uploadQuestionPaper,
  getQuestionPaper,
  getExtractionStatus,
  QuestionPaper,
  ExtractionTask,
} from '@/lib/api';
import SplitScreenReview from './SplitScreenReview';

interface QuestionPaperTabProps {
  examId: string;
  totalMarks: number;
}

type ViewMode = 'upload' | 'extracting' | 'review';

export default function QuestionPaperTab({ examId, totalMarks }: QuestionPaperTabProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('upload');
  const [questionPaper, setQuestionPaper] = useState<QuestionPaper | null>(null);
  const [extractionTask, setExtractionTask] = useState<ExtractionTask | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadQuestionPaper = useCallback(async () => {
    try {
      const qp = await getQuestionPaper(examId);
      if (qp) {
        setQuestionPaper(qp);
        if (qp.status === 'extracted' || qp.status === 'reviewed') {
          setViewMode('review');
        }
      }
    } catch (err) {
      // QP not found yet — that's fine
    }
  }, [examId]);

  const checkExtractionStatus = useCallback(async () => {
    try {
      const task = await getExtractionStatus(examId);
      if (!task) return;
      setExtractionTask(task);
      if (task.status === 'completed') {
        await loadQuestionPaper();
        setViewMode('review');
        setSuccess('Extraction complete — review and save below');
      } else if (task.status === 'failed') {
        setViewMode('upload');
        setSuccess(null);
        const errorMsg = task.error || 'Extraction failed';
        const cleanError = errorMsg.replace(/^Extraction failed:\s*/i, '');
        setError(cleanError);
      } else {
        setViewMode('extracting');
      }
    } catch {
      // No task yet or API error — keep polling
    }
  }, [examId, loadQuestionPaper]);

  useEffect(() => {
    loadQuestionPaper();
  }, [loadQuestionPaper]);

  useEffect(() => {
    if (viewMode !== 'extracting') return;

    const interval = setInterval(checkExtractionStatus, 2000);
    return () => clearInterval(interval);
  }, [viewMode, checkExtractionStatus]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      await uploadQuestionPaper(examId, file);
      setExtractionTask(null);
      setViewMode('extracting');
      checkExtractionStatus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleSaveReview = useCallback(() => {
    setSuccess('Review saved successfully');
    loadQuestionPaper();
  }, [loadQuestionPaper]);

  return (
    <div>
      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>×</button>
        </div>
      )}
      {success && (
        <div className="node node-green" style={{ marginBottom: '1rem', padding: '0.75rem', display: 'block' }}>
          {success}
          <button onClick={() => setSuccess(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Upload View */}
      {viewMode === 'upload' && (
        <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
          <h2 style={{ marginBottom: '1rem' }}>Upload Question Paper</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', maxWidth: '600px', margin: '0 auto 1.5rem' }}>
            Upload the question paper PDF. AI will automatically extract questions, marks, diagrams, and marking schemes.
            This typically takes 30-90 seconds for a 25-page paper.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', alignItems: 'center' }}>
            <label className="btn btn-primary" style={{ cursor: uploading ? 'not-allowed' : 'pointer', opacity: uploading ? 0.6 : 1 }}>
              {uploading ? 'Uploading...' : 'Select PDF'}
              <input
                type="file"
                accept=".pdf"
                onChange={handleUpload}
                disabled={uploading}
                style={{ display: 'none' }}
              />
            </label>
          </div>
          <p style={{ color: 'var(--muted)', fontSize: '0.8rem', marginTop: '1rem' }}>
            Model: gemini-2.0-flash (fast, cost-effective for extraction)
          </p>
        </div>
      )}

      {/* Extracting View */}
      {viewMode === 'extracting' && (
        <div className="panel" style={{ padding: '2rem' }}>
          <h2 style={{ marginBottom: '1.5rem' }}>Extracting Questions...</h2>

          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <span className="node node-green" style={{ fontSize: '0.75rem', minWidth: '100px' }}>Step 1</span>
              <span>Converting PDF to images</span>
              {!extractionTask || extractionTask.status === 'rasterizing' ? (
                <span className="node node-yellow" style={{ fontSize: '0.75rem' }}>In progress</span>
              ) : (
                <span className="node node-green" style={{ fontSize: '0.75rem' }}>Done</span>
              )}
            </div>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
              <span className="node node-blue" style={{ fontSize: '0.75rem', minWidth: '100px' }}>Step 2</span>
              <span>Analyzing pages with AI</span>
              {!extractionTask ? (
                <span className="node node-yellow" style={{ fontSize: '0.75rem' }}>Waiting</span>
              ) : extractionTask.status === 'analyzing' ? (
                <span className="node node-blue" style={{ fontSize: '0.75rem' }}>
                  {extractionTask.processed_pages}/{extractionTask.total_pages} pages
                </span>
              ) : extractionTask.processed_pages > 0 ? (
                <span className="node node-green" style={{ fontSize: '0.75rem' }}>Done</span>
              ) : (
                <span className="node node-yellow" style={{ fontSize: '0.75rem' }}>Waiting</span>
              )}
            </div>
            {extractionTask && extractionTask.status === 'analyzing' && (
              <div style={{ background: 'var(--surface2)', borderRadius: 'var(--radius)', height: '8px', overflow: 'hidden' }}>
                <div
                  style={{
                    width: `${(extractionTask.processed_pages / Math.max(extractionTask.total_pages, 1)) * 100}%`,
                    height: '100%',
                    background: 'var(--accent)',
                    transition: 'width 0.3s',
                  }}
                />
              </div>
            )}
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span className="node node-purple" style={{ fontSize: '0.75rem', minWidth: '100px' }}>Step 3</span>
              <span>Consolidating results</span>
              {!extractionTask ? (
                <span className="node node-yellow" style={{ fontSize: '0.75rem' }}>Waiting</span>
              ) : extractionTask.status === 'consolidating' ? (
                <span className="node node-purple" style={{ fontSize: '0.75rem' }}>In progress</span>
              ) : extractionTask.status === 'completed' ? (
                <span className="node node-green" style={{ fontSize: '0.75rem' }}>Done</span>
              ) : (
                <span className="node node-yellow" style={{ fontSize: '0.75rem' }}>Waiting</span>
              )}
            </div>
          </div>

          {extractionTask && extractionTask.questions_found_so_far > 0 && (
            <p style={{ color: 'var(--muted)', marginTop: '1rem' }}>
              Found so far: {extractionTask.questions_found_so_far} questions
            </p>
          )}

          {extractionTask?.error && (
            <p style={{ color: 'var(--red)', marginTop: '1rem' }}>Error: {extractionTask.error}</p>
          )}
        </div>
      )}

      {/* Split-Screen Review View */}
      {viewMode === 'review' && questionPaper && (
        <SplitScreenReview
          examId={examId}
          questionPaper={questionPaper}
          onSaveReview={handleSaveReview}
        />
      )}
    </div>
  );
}
