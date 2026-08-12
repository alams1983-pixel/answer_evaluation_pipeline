"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';
import Link from 'next/link';

interface Exam {
  id: string;
  title: string;
  subject_id: string;
  class_id: string;
  total_marks: number;
  scheduled_on: string | null;
  complexity_tier: string;
  grading_rubric: string;
  rubric_notes: string | null;
  answer_key_id: string | null;
  result_schema_id: string | null;
  status: string;
  created_at: string;
}

interface Class {
  id: string;
  name: string;
  section: string | null;
  session: string;
}

interface Subject {
  id: string;
  name: string;
  code: string | null;
  class_id: string;
}

interface ResultSchema {
  id: string;
  name: string;
  description: string | null;
}

const statusColors: Record<string, string> = {
  draft: 'node-yellow',
  ready: 'node-blue',
  grading: 'node-purple',
  partially_graded: 'node-orange',
  completed: 'node-green',
};

export default function ExamsPage() {
  const { user, loading: authLoading } = useAuth();
  const [exams, setExams] = useState<Exam[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [schemas, setSchemas] = useState<ResultSchema[]>([]);
  const [sessions, setSessions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionFilter, setSessionFilter] = useState<string>('all');
  const [showModal, setShowModal] = useState(false);
  const [selectedSession, setSelectedSession] = useState<string>('');
  const [formData, setFormData] = useState({
    title: '',
    subject_id: '',
    class_id: '',
    total_marks: 100,
    scheduled_on: '',
    complexity_tier: 'standard' as 'simple' | 'standard' | 'complex',
    grading_rubric: 'strict' as 'strict' | 'lenient' | 'custom',
    rubric_notes: '',
    result_schema_id: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role)) {
      loadData();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role))) {
      setLoading(false);
    }
  }, [sessionFilter, user, authLoading]);

  const loadData = async () => {
    try {
      setLoading(true);

      const [examsRes, classesRes, subjectsRes, schemasRes] = await Promise.allSettled([
        apiGet<Exam[]>('/exams/'),
        apiGet<Class[]>('/classes/'),
        apiGet<Subject[]>('/subjects/'),
        apiGet<ResultSchema[]>('/exams/result-schemas/'),
      ]);

      if (examsRes.status === 'fulfilled') setExams(examsRes.value);
      else console.error('Failed to load exams:', examsRes.reason);

      if (classesRes.status === 'fulfilled') {
        setClasses(classesRes.value);
        const uniqueSessions = [...new Set(classesRes.value.map(c => c.session).filter(Boolean))];
        setSessions(uniqueSessions);
      }
      else console.error('Failed to load classes:', classesRes.reason);

      if (subjectsRes.status === 'fulfilled') setSubjects(subjectsRes.value);
      else console.error('Failed to load subjects:', subjectsRes.reason);

      if (schemasRes.status === 'fulfilled') setSchemas(schemasRes.value);
      else console.error('Failed to load schemas:', schemasRes.reason);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      const payload = {
        title: formData.title,
        subject_id: formData.subject_id,
        class_id: formData.class_id,
        total_marks: formData.total_marks,
        scheduled_on: formData.scheduled_on || undefined,
        complexity_tier: formData.complexity_tier,
        grading_rubric: formData.grading_rubric,
        rubric_notes: formData.rubric_notes || undefined,
        result_schema_id: formData.result_schema_id || undefined,
      };

      await apiPost<Exam>('/exams/', payload);

      setShowModal(false);
      setFormData({
        title: '',
        subject_id: '',
        class_id: '',
        total_marks: 100,
        scheduled_on: '',
        complexity_tier: 'standard',
        grading_rubric: 'strict',
        rubric_notes: '',
        result_schema_id: '',
      });
      loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create exam');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (examId: string) => {
    if (!confirm('Are you sure you want to delete this exam?')) return;

    try {
      await apiDelete(`/exams/${examId}/`);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete exam');
    }
  };

  const handleClassChange = (classId: string) => {
    setFormData({ ...formData, class_id: classId, subject_id: '' });
  };

  const filteredSubjects = subjects.filter(s => s.class_id === formData.class_id);

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user || !['admin', 'teacher'].includes(user.role)) {
    return <div>Access denied</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 className="text-xl">Exams</h1>
        <button className="btn btn-primary" onClick={() => setShowModal(true)}>
          Create Exam
        </button>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div className="panel" style={{ padding: '1rem', marginBottom: '1rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <label className="label" style={{ marginBottom: 0, marginRight: '0.5rem' }}>Filter by session:</label>
        <select
          value={sessionFilter}
          onChange={(e) => setSessionFilter(e.target.value)}
          className="form-input"
          style={{ width: 'auto' }}
        >
          <option value="all">All Sessions</option>
          {sessions.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Subject</th>
                <th>Class</th>
                <th>Session</th>
                <th>Total Marks</th>
                <th>Complexity</th>
                <th>Status</th>
                <th>Answer Key</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(() => {
                const classIdsBySession = new Map<string, string[]>();
                classes.forEach(c => {
                  if (!classIdsBySession.has(c.session)) classIdsBySession.set(c.session, []);
                  classIdsBySession.get(c.session)!.push(c.id);
                });
                const allowedClassIds = sessionFilter === 'all'
                  ? null
                  : new Set(classIdsBySession.get(sessionFilter) || []);
                const filteredExams = allowedClassIds
                  ? exams.filter(e => allowedClassIds.has(e.class_id))
                  : exams;

                return filteredExams.map((exam) => {
                  const subject = subjects.find(s => s.id === exam.subject_id);
                  const cls = classes.find(c => c.id === exam.class_id);
                  const tierColors: Record<string, string> = {
                    simple: 'node-green',
                    standard: 'node-blue',
                    complex: 'node-red',
                  };
                  const tierLabels: Record<string, string> = {
                    simple: 'Simple',
                    standard: 'Standard',
                    complex: 'Complex',
                  };
                  return (
                    <tr key={exam.id}>
                      <td>
                        <Link href={`/exams/${exam.id}`} style={{ color: 'var(--accent-primary)', fontWeight: 500, textDecoration: 'none' }}>
                          {exam.title}
                        </Link>
                      </td>
                      <td>
                        {subject ? (
                          <span className="node node-purple">{subject.name}</span>
                        ) : '-'}
                      </td>
                      <td>
                        {cls ? `${cls.name}${cls.section ? ` - ${cls.section}` : ''}` : '-'}
                      </td>
                      <td>
                        {cls && cls.session ? (
                          <span className="node node-teal">{cls.session}</span>
                        ) : '-'}
                      </td>
                      <td>{exam.total_marks}</td>
                      <td>
                        <span className={`node ${tierColors[exam.complexity_tier] || 'node-yellow'}`}>
                          {tierLabels[exam.complexity_tier] || exam.complexity_tier}
                        </span>
                      </td>
                      <td>
                        <span className={`node ${statusColors[exam.status] || 'node-yellow'}`}>
                          {exam.status}
                        </span>
                      </td>
                      <td>
                        {exam.answer_key_id ? (
                          <span className="node node-green">Attached</span>
                        ) : (
                          <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Not set</span>
                        )}
                      </td>
                      <td style={{ display: 'flex', gap: '0.5rem' }}>
                        <Link href={`/exams/${exam.id}`} className="btn btn-secondary">
                          Manage
                        </Link>
                        {user?.role === 'admin' && (
                          <button
                            className="btn"
                            style={{ color: 'var(--error)' }}
                            onClick={() => handleDelete(exam.id)}
                          >
                            Delete
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                });
              })()}
              {exams.length === 0 && (
                <tr>
                  <td colSpan={9} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No exams found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => { setShowModal(false); setSelectedSession(''); setFormData(prev => ({ ...prev, class_id: '', subject_id: '' })); }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create Exam</h2>
            {formError && <div className="error-message">{formError}</div>}
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Exam Title</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                  required
                  placeholder="e.g., Mid-term Physics"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Session <span style={{ color: 'var(--error)' }}>*</span></label>
                <select
                  className="form-input"
                  value={selectedSession}
                  onChange={(e) => {
                    setSelectedSession(e.target.value);
                    setFormData(prev => ({ ...prev, class_id: '', subject_id: '' }));
                  }}
                  required
                >
                  <option value="">Select session</option>
                  {sessions.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Class <span style={{ color: 'var(--error)' }}>*</span></label>
                <select
                  className="form-input"
                  value={formData.class_id}
                  onChange={(e) => handleClassChange(e.target.value)}
                  required
                  disabled={!selectedSession}
                >
                  <option value="">Select class</option>
                  {classes
                    .filter(c => c.session === selectedSession)
                    .map((c) => (
                      <option key={c.id} value={c.id}>{c.name}{c.section ? ` - ${c.section}` : ''}</option>
                    ))}
                </select>
                {selectedSession && classes.filter(c => c.session === selectedSession).length === 0 && (
                  <p style={{ fontSize: '0.8rem', color: 'var(--warning)', marginTop: '0.25rem' }}>
                    No classes found for session "{selectedSession}". Create a class first.
                  </p>
                )}
              </div>
              <div className="form-group">
                <label className="form-label">Subject</label>
                <select
                  className="form-input"
                  value={formData.subject_id}
                  onChange={(e) => setFormData({ ...formData, subject_id: e.target.value })}
                  required
                  disabled={!formData.class_id}
                >
                  <option value="">Select subject</option>
                  {filteredSubjects.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}{s.code ? ` (${s.code})` : ''}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Total Marks</label>
                <input
                  type="number"
                  className="form-input"
                  value={formData.total_marks}
                  onChange={(e) => setFormData({ ...formData, total_marks: parseInt(e.target.value) || 0 })}
                  required
                  min={1}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Complexity Tier</label>
                <select
                  className="form-input"
                  value={formData.complexity_tier}
                  onChange={(e) => setFormData({ ...formData, complexity_tier: e.target.value as 'simple' | 'standard' | 'complex' })}
                >
                  <option value="simple">Simple (CBSE-style, text-based answers)</option>
                  <option value="standard">Standard (Mixed questions, some diagrams)</option>
                  <option value="complex">Complex (IIT-JEE/NEET, heavy diagrams, multi-step)</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Scheduled Date (optional)</label>
                <input
                  type="date"
                  className="form-input"
                  value={formData.scheduled_on}
                  onChange={(e) => setFormData({ ...formData, scheduled_on: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Grading Rubric</label>
                <select
                  className="form-input"
                  value={formData.grading_rubric}
                  onChange={(e) => setFormData({ ...formData, grading_rubric: e.target.value as 'strict' | 'lenient' | 'custom' })}
                >
                  <option value="strict">Strict</option>
                  <option value="lenient">Lenient</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Rubric Notes (optional)</label>
                <textarea
                  className="form-input"
                  value={formData.rubric_notes}
                  onChange={(e) => setFormData({ ...formData, rubric_notes: e.target.value })}
                  rows={3}
                  placeholder="Freeform hints for AI grading..."
                />
              </div>
              <div className="form-group">
                <label className="form-label">Result Schema (optional)</label>
                <select
                  className="form-input"
                  value={formData.result_schema_id}
                  onChange={(e) => setFormData({ ...formData, result_schema_id: e.target.value })}
                >
                  <option value="">None (use default)</option>
                  {schemas.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => { setShowModal(false); setSelectedSession(''); setFormData(prev => ({ ...prev, class_id: '', subject_id: '' })); }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
