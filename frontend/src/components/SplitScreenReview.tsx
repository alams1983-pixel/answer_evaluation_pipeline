"use client";

import { useState, useRef, useCallback } from 'react';
import {
  QuestionPaper,
  QPExtractedQuestion,
  AdditionalPdf,
  QuestionPaperCrop,
  getQuestionPaperPageUrl,
  getAdditionalPdfPageUrl,
  getCropImageUrl,
  createCrop,
  getAdditionalPdfs,
  reviewQuestionPaper,
} from '@/lib/api';
import PDFViewerCanvas, { PDFViewerCanvasRef } from './PDFViewerCanvas';
import CropOverlay from './CropOverlay';
import AttachedImagesSection from './AttachedImagesSection';
import AdditionalPdfUploader from './AdditionalPdfUploader';

interface SplitScreenReviewProps {
  examId: string;
  questionPaper: QuestionPaper;
  onSaveReview: () => void;
}

type PDFTab = {
  id: string;
  label: string;
  type: 'primary' | 'additional';
  pdfId?: string;
};

export default function SplitScreenReview({
  examId,
  questionPaper,
  onSaveReview,
}: SplitScreenReviewProps) {
  const [pdfTabs, setPdfTabs] = useState<PDFTab[]>([
    { id: 'primary', label: 'Question Paper (original.pdf)', type: 'primary' },
  ]);
  const [activeTab, setActiveTab] = useState('primary');
  const [currentPage, setCurrentPage] = useState(1);

  const [activeQuestionIndex, setActiveQuestionIndex] = useState<number | null>(null);
  const [editingQuestions, setEditingQuestions] = useState<QPExtractedQuestion[]>(
    questionPaper.extracted_questions.map(q => ({ ...q }))
  );
  const [expandedQuestion, setExpandedQuestion] = useState<number | null>(null);

  const [pageSelections, setSelections] = useState<Map<number, boolean>>(() => {
    const m = new Map<number, boolean>();
    questionPaper.pages.forEach(p => m.set(p.page_no, p.is_needed_for_grading));
    return m;
  });

  const [cropsByQuestion, setCropsByQuestion] = useState<Map<number, QuestionPaperCrop[]>>(() => {
    const m = new Map<number, QuestionPaperCrop[]>();
    questionPaper.extracted_questions.forEach((q, i) => {
      if (q.attached_images && q.attached_images.length > 0) {
        m.set(i, q.attached_images);
      }
    });
    return m;
  });

  const [cropMode, setCropMode] = useState(false);
  const [pendingCrop, setPendingCrop] = useState<{ rect: { x: number; y: number; width: number; height: number }; previewUrl: string } | null>(null);

  const [additionalPdfs, setAdditionalPdfs] = useState<AdditionalPdf[]>([]);
  const [loadingAdditionalPdfs, setLoadingAdditionalPdfs] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const pdfViewerRef = useRef<PDFViewerCanvasRef>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const activeTabObj = pdfTabs.find(t => t.id === activeTab);
  const isPrimaryTab = activeTabObj?.type === 'primary';

  const getPdfUrlForTab = useCallback((tab: PDFTab, pageNo: number): string => {
    if (tab.type === 'primary') {
      return getQuestionPaperPageUrl(examId, pageNo);
    }
    if (tab.pdfId) {
      return getAdditionalPdfPageUrl(examId, tab.pdfId, pageNo);
    }
    return '';
  }, [examId]);

  const totalPdfPages = isPrimaryTab
    ? questionPaper.total_pages
    : (additionalPdfs.find(p => p.id === activeTabObj?.pdfId)?.total_pages ?? 1);

  const loadAdditionalPdfs = useCallback(async () => {
    try {
      setLoadingAdditionalPdfs(true);
      const result = await getAdditionalPdfs(examId);
      const tabs: PDFTab[] = [
        { id: 'primary', label: 'Question Paper (original.pdf)', type: 'primary' },
        ...result.pdfs.map(p => ({
          id: `additional-${p.id}`,
          label: p.label,
          type: 'additional' as const,
          pdfId: p.id,
        })),
      ];
      setPdfTabs(tabs);
      setAdditionalPdfs(result.pdfs);
    } catch (err) {
      console.error('Failed to load additional PDFs:', err);
    } finally {
      setLoadingAdditionalPdfs(false);
    }
  }, [examId]);

  const handleAdditionalPdfUploaded = useCallback((pdf: AdditionalPdf) => {
    setAdditionalPdfs(prev => [...prev, pdf]);
    setPdfTabs(prev => [
      ...prev,
      {
        id: `additional-${pdf.id}`,
        label: pdf.label,
        type: 'additional',
        pdfId: pdf.id,
      },
    ]);
  }, []);

  const handleCropComplete = useCallback((rect: { x: number; y: number; width: number; height: number }, previewUrl: string) => {
    setPendingCrop({ rect, previewUrl });
  }, []);

  const handleAttachCrop = useCallback(async () => {
    if (!pendingCrop || activeQuestionIndex === null) return;

    const question = editingQuestions[activeQuestionIndex];
    if (!question) return;

    try {
      const base64Data = pendingCrop.previewUrl.split(',')[1];
      const result = await createCrop(examId, {
        question_index: activeQuestionIndex,
        q_no: question.q_no,
        page_no: currentPage,
        source_pdf: activeTabObj?.label ?? 'original.pdf',
        bbox: {
          x: Math.round(pendingCrop.rect.x),
          y: Math.round(pendingCrop.rect.y),
          width: Math.round(pendingCrop.rect.width),
          height: Math.round(pendingCrop.rect.height),
        },
        image_data_base64: base64Data,
      });

      setCropsByQuestion(prev => {
        const next = new Map(prev);
        const existing = next.get(activeQuestionIndex) ?? [];
        next.set(activeQuestionIndex, [...existing, result.crop]);
        return next;
      });

      setEditingQuestions(prev => {
        const updated = [...prev];
        const existing = updated[activeQuestionIndex].attached_images ?? [];
        updated[activeQuestionIndex] = {
          ...updated[activeQuestionIndex],
          attached_images: [...existing, result.crop],
        };
        return updated;
      });

      setPendingCrop(null);
      setCropMode(false);
      setSuccess(`Image attached to Q${question.q_no}`);
      setTimeout(() => setSuccess(null), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to attach crop');
    }
  }, [pendingCrop, activeQuestionIndex, editingQuestions, examId, currentPage, activeTabObj]);

  const handleRemoveCrop = useCallback((questionIndex: number, cropId: string) => {
    setCropsByQuestion(prev => {
      const next = new Map(prev);
      const existing = next.get(questionIndex) ?? [];
      next.set(questionIndex, existing.filter(c => c.id !== cropId));
      return next;
    });

    setEditingQuestions(prev => {
      const updated = [...prev];
      const existing = updated[questionIndex].attached_images ?? [];
      updated[questionIndex] = {
        ...updated[questionIndex],
        attached_images: existing.filter(c => c.id !== cropId),
      };
      return updated;
    });
  }, []);

  const handleSaveReview = async () => {
    setSaving(true);
    setError(null);
    try {
      const included: number[] = [];
      const excluded: number[] = [];
      pageSelections.forEach((selected, pageNo) => {
        if (selected) included.push(pageNo);
        else excluded.push(pageNo);
      });

      await reviewQuestionPaper(examId, included, excluded, editingQuestions);
      setSuccess('Review saved successfully');
      onSaveReview();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save review');
    } finally {
      setSaving(false);
    }
  };

  const selectAllPages = () => {
    const next = new Map<number, boolean>();
    questionPaper.pages.forEach(p => next.set(p.page_no, true));
    setSelections(next);
  };

  const deselectUnusedPages = () => {
    const next = new Map<number, boolean>();
    questionPaper.pages.forEach(p => next.set(p.page_no, p.is_needed_for_grading));
    setSelections(next);
  };

  const togglePage = (pageNo: number) => {
    setSelections(prev => {
      const next = new Map(prev);
      next.set(pageNo, !prev.get(pageNo));
      return next;
    });
  };

  const includedCount = Array.from(pageSelections.values()).filter(Boolean).length;
  const activeQuestion = activeQuestionIndex !== null ? editingQuestions[activeQuestionIndex] : null;

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

      {/* Tab bar for PDFs */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
        {pdfTabs.map(tab => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => { setActiveTab(tab.id); setCurrentPage(1); setPendingCrop(null); }}
            style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
          >
            {tab.label}
          </button>
        ))}
        <button
          className="btn btn-secondary"
          onClick={loadAdditionalPdfs}
          style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginLeft: '0.5rem' }}
        >
          Refresh PDFs
        </button>
      </div>

      {/* Split-screen layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '60% 40%', gap: '1rem', minHeight: '600px' }}>
        {/* Left panel: PDF Viewer */}
        <div className="panel" style={{ padding: '0.75rem', position: 'relative', overflow: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button
                className="btn btn-secondary"
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage(p => p - 1)}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              >
                ← Prev
              </button>
              <span style={{ color: 'var(--muted)', fontSize: '0.85rem' }}>
                Page {currentPage} / {totalPdfPages}
              </span>
              <button
                className="btn btn-secondary"
                disabled={currentPage >= totalPdfPages}
                onClick={() => setCurrentPage(p => p + 1)}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
              >
                Next →
              </button>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                className={cropMode ? 'btn btn-primary' : 'btn btn-secondary'}
                onClick={() => {
                  setCropMode(!cropMode);
                  setPendingCrop(null);
                }}
                style={{ padding: '0.3rem 0.8rem', fontSize: '0.8rem' }}
              >
                {cropMode ? '✂️ Crop Mode ON' : '✂️ Crop Mode'}
              </button>
            </div>
          </div>

          {/* Active question indicator */}
          {activeQuestion && (
            <div style={{ marginBottom: '0.5rem', padding: '0.4rem 0.75rem', background: 'rgba(79, 142, 247, 0.1)', borderRadius: 'var(--radius)', border: '1px solid var(--accent)', fontSize: '0.8rem' }}>
              <span className="node node-blue" style={{ fontSize: '0.7rem', marginRight: '0.5rem' }}>
                Active: Q{activeQuestion.q_no}
              </span>
              <span style={{ color: 'var(--muted)' }}>
                Crop an image region and it will be attached to this question
              </span>
            </div>
          )}

          <div style={{ position: 'relative' }}>
            <PDFViewerCanvas
              ref={pdfViewerRef}
              imageUrl={getPdfUrlForTab(activeTabObj!, currentPage)}
              onImageReady={(canvas) => {
                canvasRef.current = canvas;
              }}
            />
            {cropMode && (
              <CropOverlay
                canvasRef={canvasRef as React.RefObject<HTMLCanvasElement | null>}
                pageWidth={pdfViewerRef.current?.getPageWidth() ?? 1000}
                pageHeight={pdfViewerRef.current?.getPageHeight() ?? 1400}
                onCropComplete={handleCropComplete}
                disabled={!cropMode}
              />
            )}
          </div>

          {/* Pending crop popup — floating overlay */}
          {/* Pending crop popup — floating overlay */}
          {pendingCrop && (
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0, 0, 0, 0.65)',
                backdropFilter: 'blur(8px)',
                WebkitBackdropFilter: 'blur(8px)',
                zIndex: 999999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '1.5rem',
              }}
              onClick={() => setPendingCrop(null)}
            >
              <div
                style={{
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-xl)',
                  padding: '1.75rem',
                  maxWidth: '520px',
                  width: '100%',
                  boxShadow: 'var(--shadow-xl)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '1.25rem',
                }}
                onClick={(e) => e.stopPropagation()}
              >
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                    Crop Region Preview
                  </h3>
                  <button
                    onClick={() => setPendingCrop(null)}
                    style={{
                      background: 'none',
                      border: 'none',
                      fontSize: '1.25rem',
                      cursor: 'pointer',
                      color: 'var(--text-secondary)',
                      lineHeight: 1,
                    }}
                    aria-label="Close"
                  >
                    ✕
                  </button>
                </div>

                {/* Preview Image Container */}
                <div
                  style={{
                    textAlign: 'center',
                    background: 'var(--bg-tertiary)',
                    padding: '1rem',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--border-subtle)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <img
                    src={pendingCrop.previewUrl}
                    alt="Crop preview"
                    style={{
                      maxWidth: '100%',
                      maxHeight: '260px',
                      objectFit: 'contain',
                      borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-subtle)',
                      boxShadow: 'var(--shadow-sm)',
                      background: '#ffffff',
                    }}
                  />
                  <span style={{ marginTop: '0.6rem', fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Captured Region: {Math.round(pendingCrop.rect.width)} × {Math.round(pendingCrop.rect.height)} px
                  </span>
                </div>

                {/* Question Info Banner */}
                <div
                  style={{
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    background: activeQuestionIndex !== null ? 'var(--accent-muted)' : 'var(--warning-bg)',
                    border: `1px solid ${activeQuestionIndex !== null ? 'var(--accent-primary)' : 'var(--warning)'}`,
                    fontSize: '0.9rem',
                    color: activeQuestionIndex !== null ? 'var(--accent-primary)' : 'var(--warning-text)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span style={{ fontWeight: 600 }}>
                    {activeQuestionIndex !== null
                      ? `Target Question: Q${editingQuestions[activeQuestionIndex].q_no}`
                      : '⚠️ No Question Selected'}
                  </span>
                  <span style={{ fontSize: '0.85rem', opacity: 0.85 }}>
                    {activeQuestionIndex !== null
                      ? `(${editingQuestions[activeQuestionIndex].marks} marks)`
                      : 'Select question on right panel'}
                  </span>
                </div>

                {/* Buttons */}
                <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end', paddingTop: '0.25rem' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={() => setPendingCrop(null)}
                    style={{ padding: '0.6rem 1.4rem', fontWeight: 600 }}
                  >
                    Cancel
                  </button>
                  <button
                    className="btn btn-primary"
                    disabled={activeQuestionIndex === null}
                    onClick={handleAttachCrop}
                    style={{ padding: '0.6rem 1.4rem', fontWeight: 600 }}
                  >
                    Attach to Q{activeQuestionIndex !== null ? editingQuestions[activeQuestionIndex].q_no : '?'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Additional PDF uploader */}
          <div style={{ marginTop: '1rem' }}>
            <AdditionalPdfUploader
              examId={examId}
              onUploadComplete={handleAdditionalPdfUploaded}
            />
          </div>
        </div>

        {/* Right panel: Questions list */}
        <div className="panel" style={{ padding: '0.75rem', overflow: 'auto' }}>
          <h3 style={{ marginBottom: '1rem', fontSize: '1rem' }}>
            Extracted Questions ({editingQuestions.length})
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {editingQuestions.map((q, i) => (
              <div
                key={i}
                style={{
                  padding: '0.75rem',
                  borderRadius: 'var(--radius)',
                  border: activeQuestionIndex === i ? '2px solid var(--accent)' : '1px solid var(--border)',
                  background: activeQuestionIndex === i ? 'rgba(79, 142, 247, 0.08)' : 'var(--surface2)',
                  cursor: 'pointer',
                }}
                onClick={() => {
                  setActiveQuestionIndex(i);
                  setExpandedQuestion(expandedQuestion === i ? null : i);
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <span className="node node-blue" style={{ fontSize: '0.75rem' }}>{q.q_no}</span>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                      {q.marks} marks
                    </span>
                    {q.has_diagram && (
                      <span className="node node-orange" style={{ fontSize: '0.7rem' }}>Diagram</span>
                    )}
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--muted)' }}>
                    {expandedQuestion === i ? '▼' : '▶'}
                  </span>
                </div>

                <p style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {q.question || '(no question text)'}
                </p>

                {/* Attached images preview */}
                {cropsByQuestion.get(i) && cropsByQuestion.get(i)!.length > 0 && (
                  <div style={{ marginTop: '0.5rem', display: 'flex', gap: '0.25rem' }}>
                    {cropsByQuestion.get(i)!.slice(0, 3).map(crop => (
                      <img
                        key={crop.id}
                        src={getCropImageUrl(examId, crop.id)}
                        alt={`Q${crop.q_no} crop`}
                        style={{ width: '32px', height: '32px', objectFit: 'contain', borderRadius: '2px', border: '1px solid var(--border)' }}
                      />
                    ))}
                    {cropsByQuestion.get(i)!.length > 3 && (
                      <span style={{ fontSize: '0.7rem', color: 'var(--muted)', alignSelf: 'center' }}>
                        +{cropsByQuestion.get(i)!.length - 3} more
                      </span>
                    )}
                  </div>
                )}

                {/* Expanded edit form */}
                {expandedQuestion === i && (
                  <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label className="label">Question Number</label>
                      <input
                        type="text"
                        className="input-field"
                        value={q.q_no}
                        onChange={(e) => {
                          const updated = [...editingQuestions];
                          updated[i] = { ...updated[i], q_no: e.target.value };
                          setEditingQuestions(updated);
                        }}
                      />
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label className="label">Marks</label>
                      <input
                        type="number"
                        className="input-field"
                        value={q.marks}
                        onChange={(e) => {
                          const updated = [...editingQuestions];
                          updated[i] = { ...updated[i], marks: parseInt(e.target.value) || 0 };
                          setEditingQuestions(updated);
                        }}
                        min={0}
                      />
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label className="label">Question Text</label>
                      <textarea
                        className="input-field"
                        value={q.question || ''}
                        onChange={(e) => {
                          const updated = [...editingQuestions];
                          updated[i] = { ...updated[i], question: e.target.value || null };
                          setEditingQuestions(updated);
                        }}
                        rows={3}
                      />
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label className="label">Expected Answer</label>
                      <textarea
                        className="input-field"
                        value={q.expected_answer || ''}
                        onChange={(e) => {
                          const updated = [...editingQuestions];
                          updated[i] = { ...updated[i], expected_answer: e.target.value || null };
                          setEditingQuestions(updated);
                        }}
                        rows={3}
                      />
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label className="label">Marking Scheme</label>
                      <textarea
                        className="input-field"
                        value={q.marking_scheme || ''}
                        onChange={(e) => {
                          const updated = [...editingQuestions];
                          updated[i] = { ...updated[i], marking_scheme: e.target.value || null };
                          setEditingQuestions(updated);
                        }}
                        rows={2}
                      />
                    </div>
                    <div style={{ marginBottom: '0.75rem' }}>
                      <label className="label">Keywords (comma-separated)</label>
                      <input
                        type="text"
                        className="input-field"
                        value={q.keywords.join(', ')}
                        onChange={(e) => {
                          const updated = [...editingQuestions];
                          updated[i] = {
                            ...updated[i],
                            keywords: e.target.value.split(',').map(k => k.trim()).filter(Boolean),
                          };
                          setEditingQuestions(updated);
                        }}
                      />
                    </div>

                    {/* Attached Images Section */}
                    <AttachedImagesSection
                      examId={examId}
                      crops={cropsByQuestion.get(i) ?? []}
                      onRemove={(cropId) => handleRemoveCrop(i, cropId)}
                    />

                    <div style={{ marginTop: '0.75rem', padding: '0.5rem', background: 'rgba(79, 142, 247, 0.08)', borderRadius: 'var(--radius)', fontSize: '0.8rem', color: 'var(--muted)' }}>
                      <span className="node node-teal" style={{ fontSize: '0.7rem' }}>Tip</span>
                      {' '}Enable "Crop Mode" on the left, draw a region, and click "Attach to Q{q.q_no}"
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {questionPaper.warnings && questionPaper.warnings.length > 0 && (
            <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'rgba(245, 158, 11, 0.1)', borderRadius: 'var(--radius)', border: '1px solid var(--yellow)' }}>
              <strong style={{ color: 'var(--yellow)' }}>Warnings:</strong>
              <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.5rem', color: 'var(--text-secondary)' }}>
                {questionPaper.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Pages for Grading section */}
      <div style={{ marginTop: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h3 style={{ fontSize: '1rem' }}>Pages for Grading ({includedCount}/{questionPaper.total_pages})</h3>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button className="btn btn-secondary" onClick={selectAllPages} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>Select All</button>
            <button className="btn btn-secondary" onClick={deselectUnusedPages} style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}>Deselect Unused</button>
          </div>
        </div>

        <div className="panel" style={{ padding: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.75rem' }}>
            {questionPaper.pages.map(p => (
              <div
                key={p.page_no}
                style={{
                  padding: '0.75rem',
                  borderRadius: 'var(--radius)',
                  border: '1px solid var(--border)',
                  background: pageSelections.get(p.page_no) ? 'rgba(34, 197, 94, 0.08)' : 'var(--surface2)',
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.5rem',
                }}
              >
                <input
                  type="checkbox"
                  checked={pageSelections.get(p.page_no) || false}
                  onChange={() => togglePage(p.page_no)}
                  style={{ width: '18px', height: '18px', cursor: 'pointer', marginTop: '2px' }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                    <span className="node node-blue" style={{ fontSize: '0.7rem' }}>Pg {p.page_no}</span>
                    {p.is_instruction_page && <span className="node node-yellow" style={{ fontSize: '0.65rem' }}>Instructions</span>}
                    {p.has_diagrams && <span className="node node-orange" style={{ fontSize: '0.65rem' }}>Diagrams</span>}
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--muted)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.reason}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Save button bar */}
      <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
        <button
          className="btn btn-primary"
          onClick={handleSaveReview}
          disabled={saving}
          style={{ padding: '0.6rem 2rem' }}
        >
          {saving ? 'Saving...' : 'Save & Continue'}
        </button>
      </div>
    </div>
  );
}
