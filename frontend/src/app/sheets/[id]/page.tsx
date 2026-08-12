"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPatch, apiPost, getPageImageUrl, Grading } from '@/lib/api';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import SchemaFormRenderer from '@/components/SchemaFormRenderer';
import ZoomModal from '@/app/exams/[id]/upload/components/ZoomModal';

interface AnswerSheet {
  id: string;
  exam_id: string;
  student_name: string | null;
  roll_no: string | null;
  class_label: string | null;
  status: string;
  page_count: number;
}

interface Exam {
  id: string;
  title: string;
  result_schema_id: string | null;
}

interface ResultSchema {
  id: string;
  name: string;
  schema_definition: Record<string, unknown>;
}

interface OverrideEntry {
  by: string;
  at: string;
  patch: Record<string, unknown>;
}

export default function SheetReviewPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const router = useRouter();
  const sheetId = params.id as string;

  const [sheet, setSheet] = useState<AnswerSheet | null>(null);
  const [exam, setExam] = useState<Exam | null>(null);
  const [grading, setGrading] = useState<Grading | null>(null);
  const [resultSchema, setResultSchema] = useState<ResultSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [showZoom, setShowZoom] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(0);
  const [showAuditLog, setShowAuditLog] = useState(false);
  const [editResult, setEditResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      loadData();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [sheetId, user, authLoading]);

  const loadData = async () => {
    try {
      setLoading(true);
      const sheetData = await apiGet<AnswerSheet>(`/exams/sheets/${sheetId}`);
      setSheet(sheetData);

      const examData = await apiGet<Exam>(`/exams/${sheetData.exam_id}/`);
      setExam(examData);

      try {
        const gradingData = await apiGet<Grading>(`/exams/sheets/${sheetId}/grading`);
        setGrading(gradingData);
        setEditResult(gradingData.result as Record<string, unknown>);
      } catch {
        setError('No grading found for this sheet. The batch may still be processing.');
      }

      if (examData.result_schema_id) {
        const schemaData = await apiGet<ResultSchema>(`/exams/result-schemas/${examData.result_schema_id}/`);
        setResultSchema(schemaData);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!grading || !editResult) return;
    try {
      setSaving(true);
      setSuccess(null);
      await apiPatch(`/exams/gradings/${grading.id}`, { result: editResult });
      setSuccess('Changes saved successfully');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!grading) return;
    if (!confirm('Publish this grading? The student will be able to see the results.')) return;
    try {
      setPublishing(true);
      await apiPost(`/exams/gradings/${grading.id}/publish`, {});
      setSuccess('Grading published successfully');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish grading');
    } finally {
      setPublishing(false);
    }
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user) {
    return <div>Access denied</div>;
  }

  if (!sheet || !exam) {
    return <div>Sheet not found</div>;
  }

  const isTeacher = ['admin', 'teacher'].includes(user.role!);
  const isPublished = grading?.status === 'published';

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <Link href={`/exams/${exam.id}`} className="btn btn-secondary" style={{ marginBottom: '0.5rem' }}>
          &larr; Back to Exam
        </Link>
        <h1 className="text-xl" style={{ marginBottom: '0.25rem' }}>Sheet Review &mdash; {sheet.student_name || 'Unknown'} (Roll: {sheet.roll_no || 'N/A'})</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', color: 'var(--text-secondary)' }}>
          <span>{exam.title}</span>
          <span className={`node node-${isPublished ? 'green' : grading?.status === 'auto' ? 'blue' : 'yellow'}`}>
            {grading?.status || 'pending'}
          </span>
          {grading && (
            <span style={{ fontWeight: 600 }}>
              {grading.total_awarded} / {grading.total_max} marks
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      {success && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--success-bg)', border: '1px solid var(--success)', borderRadius: 'var(--radius-md)', color: 'var(--success-text)', fontSize: '0.875rem' }}>
          {success}
          <button onClick={() => setSuccess(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div className="panel" style={{ padding: '1.5rem' }}>
          <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '1rem' }}>Answer Sheet Pages</h3>
          <div style={{ textAlign: 'center', marginBottom: '1rem' }}>
            <div
              style={{
                cursor: 'pointer',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-md)',
                overflow: 'hidden',
                display: 'inline-block',
                maxWidth: '100%',
              }}
              onClick={() => setShowZoom(getPageImageUrl(sheetId, currentPage + 1))}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={getPageImageUrl(sheetId, currentPage + 1)}
                alt={`Page ${currentPage + 1}`}
                style={{ maxWidth: '100%', height: 'auto' }}
              />
            </div>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.5rem' }}>
              Page {currentPage + 1} of {sheet.page_count} &mdash; Click to zoom
            </p>
          </div>
          {sheet.page_count > 1 && (
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
              <button
                className="btn btn-secondary"
                disabled={currentPage === 0}
                onClick={() => setCurrentPage(currentPage - 1)}
              >
                Prev
              </button>
              {Array.from({ length: sheet.page_count }, (_, i) => (
                <button
                  key={i}
                  className="btn"
                  style={{
                    background: currentPage === i ? 'var(--accent-primary)' : 'var(--bg-tertiary)',
                    color: currentPage === i ? '#fff' : 'var(--text-primary)',
                    border: 'none',
                  }}
                  onClick={() => setCurrentPage(i)}
                >
                  {i + 1}
                </button>
              ))}
              <button
                className="btn btn-secondary"
                disabled={currentPage === sheet.page_count - 1}
                onClick={() => setCurrentPage(currentPage + 1)}
              >
                Next
              </button>
            </div>
          )}
        </div>

        <div className="panel" style={{ padding: '1.5rem' }}>
          <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '1rem' }}>Grading Result</h3>

          {editResult && resultSchema ? (
            <div style={{ maxHeight: '500px', overflow: 'auto', marginBottom: '1rem' }}>
              <SchemaFormRenderer
                schema={resultSchema.schema_definition as any}
                value={editResult}
                onChange={setEditResult}
                readOnly={!isTeacher || isPublished}
              />
            </div>
          ) : editResult ? (
            <div style={{ maxHeight: '500px', overflow: 'auto', marginBottom: '1rem' }}>
              <pre style={{ fontSize: '0.8rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-muted)' }}>
                {JSON.stringify(editResult, null, 2)}
              </pre>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>No result schema attached.</p>
          )}

          {isTeacher && !isPublished && (
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
              <button className="btn btn-secondary" onClick={handlePublish} disabled={publishing} style={{ color: 'var(--success)', border: '1px solid var(--success)' }}>
                {publishing ? 'Publishing...' : 'Publish'}
              </button>
            </div>
          )}

          {isPublished && (
            <div className="node node-green" style={{ display: 'inline-block', marginTop: '0.5rem' }}>
              Published &mdash; No further changes allowed
            </div>
          )}

          {grading && grading.override_log && grading.override_log.length > 0 && (
            <div style={{ marginTop: '1.5rem' }}>
              <button className="btn btn-secondary" style={{ width: '100%' }} onClick={() => setShowAuditLog(!showAuditLog)}>
                {showAuditLog ? '\u25BC' : '\u25B6'} Audit Log ({grading.override_log.length} entries)
              </button>
              {showAuditLog && (
                <div style={{ marginTop: '0.75rem', maxHeight: '300px', overflow: 'auto' }}>
                  {(grading.override_log as OverrideEntry[]).map((entry, i) => (
                    <div key={i} className="panel" style={{ padding: '0.75rem', marginBottom: '0.5rem' }}>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>
                        Modified by {entry.by.slice(-8)} at {new Date(entry.at).toLocaleString()}
                      </div>
                      <pre style={{ fontSize: '0.7rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                        {JSON.stringify(entry.patch, null, 2)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {showZoom && (
        <ZoomModal imageUrl={showZoom} onClose={() => setShowZoom(null)} />
      )}
    </div>
  );
}
