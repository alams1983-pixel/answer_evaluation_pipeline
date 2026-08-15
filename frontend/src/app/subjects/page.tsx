"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';

interface Subject {
  id: string;
  name: string;
  code: string | null;
  class_id: string;
  teacher_ids: string[];
  created_at: string;
}

interface Class {
  id: string;
  name: string;
  section: string | null;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export default function SubjectsPage() {
  const { user, loading: authLoading } = useAuth();
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [teachers, setTeachers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [classFilter, setClassFilter] = useState<string>('all');
  const [showModal, setShowModal] = useState(false);
  const [editingSubject, setEditingSubject] = useState<Subject | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    code: '',
    class_id: '',
    teacher_ids: [] as string[],
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role)) {
      loadData();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role))) {
      setLoading(false);
    }
  }, [classFilter, user, authLoading]);

  const loadData = async () => {
    try {
      setLoading(true);
      const classParam = classFilter !== 'all' ? `?class_id=${classFilter}` : '';
      const [subjectsData, classesData, teachersData] = await Promise.all([
        apiGet<Subject[]>(`/subjects/${classParam}`),
        apiGet<Class[]>('/classes/'),
        apiGet<User[]>('/users/?role=teacher'),
      ]);
      setSubjects(subjectsData);
      setClasses(classesData);
      setTeachers(teachersData);
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
        name: formData.name,
        code: formData.code || undefined,
        class_id: formData.class_id,
        teacher_ids: formData.teacher_ids,
      };

      if (editingSubject) {
        await apiPatch<Subject>(`/subjects/${editingSubject.id}/`, payload);
      } else {
        await apiPost<Subject>('/subjects/', payload);
      }

      setShowModal(false);
      setEditingSubject(null);
      setFormData({ name: '', code: '', class_id: '', teacher_ids: [] });
      loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save subject');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (subject: Subject) => {
    setEditingSubject(subject);
    setFormData({
      name: subject.name,
      code: subject.code || '',
      class_id: subject.class_id,
      teacher_ids: subject.teacher_ids,
    });
    setShowModal(true);
  };

  const handleDelete = async (subjectId: string) => {
    if (!confirm('Are you sure you want to delete this subject?')) return;

    try {
      await apiDelete(`/subjects/${subjectId}/`);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete subject');
    }
  };

  const toggleTeacher = (teacherId: string) => {
    setFormData(prev => ({
      ...prev,
      teacher_ids: prev.teacher_ids.includes(teacherId)
        ? prev.teacher_ids.filter(id => id !== teacherId)
        : [...prev.teacher_ids, teacherId],
    }));
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user || !['admin', 'teacher'].includes(user.role)) {
    return <div>Access denied</div>;
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1 className="text-xl">Subjects</h1>
        <button
          className="btn btn-primary"
          onClick={() => {
            setEditingSubject(null);
            setFormData({ name: '', code: '', class_id: '', teacher_ids: [] });
            setShowModal(true);
          }}
        >
          Create Subject
        </button>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div className="panel" style={{ padding: '1rem', marginBottom: '1rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
        <label className="label" style={{ marginBottom: 0, marginRight: '0.5rem' }}>Filter by class:</label>
        <select
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          className="form-input"
          style={{ width: 'auto' }}
        >
          <option value="all">All Classes</option>
          {classes.map((c) => (
            <option key={c.id} value={c.id}>{c.name}{c.section ? ` - ${c.section}` : ''}</option>
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
                <th>Name</th>
                <th>Code</th>
                <th>Class</th>
                <th>Teachers</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((subject) => {
                const cls = classes.find(c => c.id === subject.class_id);
                return (
                  <tr key={subject.id}>
                    <td style={{ fontWeight: 500 }}>{subject.name}</td>
                    <td>
                      {subject.code ? (
                        <span className="node node-purple">{subject.code}</span>
                      ) : '-'}
                    </td>
                    <td>
                      {cls ? `${cls.name}${cls.section ? ` - ${cls.section}` : ''}` : '-'}
                    </td>
                    <td>
                      {subject.teacher_ids.length > 0 ? (
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                          {subject.teacher_ids.map(tid => {
                            const teacher = teachers.find(t => t.id === tid);
                            return teacher ? (
                              <span key={tid} className="node node-blue">
                                {teacher.full_name}
                              </span>
                            ) : null;
                          })}
                        </div>
                      ) : (
                        <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>No teachers assigned</span>
                      )}
                    </td>
                    <td style={{ display: 'flex', gap: '0.5rem' }}>
                      <button
                        className="btn btn-secondary"
                        onClick={() => handleEdit(subject)}
                      >
                        Edit
                      </button>
                      {(user?.role === 'admin' || (user?.role === 'teacher' && subject.teacher_ids.includes(user.id))) && (
                        <button
                          className="btn"
                          style={{ color: 'var(--error)' }}
                          onClick={() => handleDelete(subject.id)}
                        >
                          Delete
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {subjects.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No subjects found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>{editingSubject ? 'Edit Subject' : 'Create Subject'}</h2>
            {formError && <div className="error-message">{formError}</div>}
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Subject Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Subject Code (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.code}
                  onChange={(e) => setFormData({ ...formData, code: e.target.value })}
                  placeholder="e.g., PHY"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Class</label>
                <select
                  className="form-input"
                  value={formData.class_id}
                  onChange={(e) => setFormData({ ...formData, class_id: e.target.value })}
                  required
                >
                  <option value="">Select class</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}{c.section ? ` - ${c.section}` : ''}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Assign Teachers</label>
                <div style={{ maxHeight: '200px', overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: '0.5rem' }}>
                  {teachers.map(teacher => (
                    <label key={teacher.id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={formData.teacher_ids.includes(teacher.id)}
                        onChange={() => toggleTeacher(teacher.id)}
                      />
                      {teacher.full_name} ({teacher.email})
                    </label>
                  ))}
                  {teachers.length === 0 && (
                    <p style={{ color: 'var(--text-secondary)', padding: '0.5rem' }}>No teachers available</p>
                  )}
                </div>
              </div>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : editingSubject ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
