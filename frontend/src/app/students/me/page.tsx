"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, Grading, AnswerSheet, getSheet } from '@/lib/api';
import Link from 'next/link';

interface PublishedGrading {
  grading: Grading;
  sheet: AnswerSheet | null;
  exam: {
    id: string;
    title: string;
    subject_name: string;
    class_name: string;
  };
}

export default function StudentResultsPage() {
  const { user, loading: authLoading } = useAuth();
  const [results, setResults] = useState<PublishedGrading[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user) {
      loadData();
    } else if (!authLoading && !user) {
      setLoading(false);
    }
  }, [user, authLoading]);

  const loadData = async () => {
    if (!user || user.role !== 'student') return;
    try {
      setLoading(true);

      const gradings = await apiGet<Grading[]>('/students/me/gradings');

      const enriched: PublishedGrading[] = [];
      for (const grading of gradings) {
        let sheet: AnswerSheet | null = null;
        let examInfo = { id: grading.exam_id, title: 'Unknown', subject_name: '', class_name: '' };

        try {
          sheet = await getSheet(grading.sheet_id);
        } catch {
          // Sheet might be deleted or inaccessible
        }

        try {
          const exam = await apiGet<{ id: string; title: string; subject_id: string | null; class_id: string | null }>(`/exams/${grading.exam_id}/`);
          examInfo.id = exam.id;
          examInfo.title = exam.title;

          if (exam.subject_id) {
            try {
              const subject = await apiGet<{ name: string }>(`/subjects/${exam.subject_id}/`);
              examInfo.subject_name = subject.name;
            } catch {
              examInfo.subject_name = 'Unknown Subject';
            }
          }

          if (exam.class_id) {
            try {
              const cls = await apiGet<{ name: string; section: string | null }>(`/classes/${exam.class_id}/`);
              examInfo.class_name = `${cls.name}${cls.section ? ` - ${cls.section}` : ''}`;
            } catch {
              examInfo.class_name = 'Unknown Class';
            }
          }
        } catch {
          examInfo.title = 'Unknown Exam';
        }

        enriched.push({ grading, sheet, exam: examInfo });
      }

      setResults(enriched);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load results');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user) {
    return <div>Please log in to view your results.</div>;
  }

  if (user.role !== 'student') {
    return (
      <div>
        <p>Student portal is only accessible to students.</p>
        <Link href="/" className="btn btn-primary" style={{ marginTop: '1rem' }}>
          Go to Dashboard
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl" style={{ marginBottom: '1.5rem' }}>My Results</h1>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      {results.length === 0 ? (
        <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-muted)' }}>No published results yet. Your teacher will publish results when they are ready.</p>
        </div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Exam</th>
                <th>Subject</th>
                <th>Class</th>
                <th style={{ textAlign: 'center' }}>Score</th>
                <th style={{ textAlign: 'center' }}>Published</th>
                <th style={{ textAlign: 'center' }}>Details</th>
              </tr>
            </thead>
            <tbody>
              {results.map(({ grading, exam }) => {
                const pct = grading.total_max > 0 ? Math.round((grading.total_awarded / grading.total_max) * 100) : 0;
                const scoreColor = pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)';
                const isExpanded = expandedId === grading.id;

                return (
                  <tr key={grading.id}>
                    <td style={{ fontWeight: 600 }}>{exam.title}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{exam.subject_name}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{exam.class_name}</td>
                    <td style={{ textAlign: 'center' }}>
                      <span style={{ fontWeight: 700, color: scoreColor }}>
                        {grading.total_awarded}/{grading.total_max}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '0.5rem' }}>({pct}%)</span>
                    </td>
                    <td style={{ textAlign: 'center', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {grading.published_at ? new Date(grading.published_at).toLocaleDateString() : '-'}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        className="btn btn-secondary"
                        onClick={() => setExpandedId(isExpanded ? null : grading.id)}
                      >
                        {isExpanded ? 'Hide' : 'View'} Details
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {expandedId && (
        <div className="panel" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
          <PerQuestionBreakdown result={results.find(r => r.grading.id === expandedId)?.grading.result as Record<string, unknown>} />
        </div>
      )}
    </div>
  );
}

function PerQuestionBreakdown({ result }: { result: Record<string, unknown> }) {
  const questions = result?.questions as Array<{
    q_no: string;
    awarded: number;
    max: number;
    feedback?: string;
    page_refs?: number[];
    confidence?: number;
  }> | undefined;

  if (!questions || questions.length === 0) {
    return <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>No question-level breakdown available.</p>;
  }

  return (
    <div>
      <h4 className="text-md" style={{ fontWeight: 600, marginBottom: '0.75rem' }}>Question-wise Breakdown</h4>
      <div className="table-container">
        <table className="table">
          <thead>
            <tr>
              <th>Question</th>
              <th style={{ textAlign: 'center' }}>Awarded</th>
              <th style={{ textAlign: 'center' }}>Max</th>
              <th style={{ textAlign: 'center' }}>Confidence</th>
              <th>Feedback</th>
            </tr>
          </thead>
          <tbody>
            {questions.map((q, i) => {
              const pct = q.max > 0 ? Math.round((q.awarded / q.max) * 100) : 0;
              const color = pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)';
              return (
                <tr key={i}>
                  <td>
                    <span className="node node-blue">{q.q_no}</span>
                  </td>
                  <td style={{ textAlign: 'center', fontWeight: 600, color }}>
                    {q.awarded}
                  </td>
                  <td style={{ textAlign: 'center' }}>{q.max}</td>
                  <td style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                    {q.confidence !== undefined ? `${Math.round(q.confidence * 100)}%` : '-'}
                  </td>
                  <td style={{ color: 'var(--text-muted)' }}>
                    {q.feedback || '-'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {result?.overall_feedback && (
        <div style={{ marginTop: '1rem', padding: '0.75rem', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
          <strong style={{ fontSize: '0.875rem' }}>Overall Feedback:</strong>
          <p style={{ marginTop: '0.25rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            {result.overall_feedback as string}
          </p>
        </div>
      )}
    </div>
  );
}
