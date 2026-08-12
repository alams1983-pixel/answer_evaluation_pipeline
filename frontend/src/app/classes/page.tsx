"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete } from '@/lib/api';

interface Class {
  id: string;
  name: string;
  section: string | null;
  session: string;
  teacher_ids: string[];
  class_teacher_id: string | null;
  created_at: string;
}

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
}

export default function ClassesPage() {
  const { user, loading: authLoading } = useAuth();
  const [classes, setClasses] = useState<Class[]>([]);
  const [teachers, setTeachers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingClass, setEditingClass] = useState<Class | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    section: '',
    session: '',
    teacher_ids: [] as string[],
    class_teacher_id: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role)) {
      loadData();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role))) {
      setLoading(false);
    }
  }, [user, authLoading]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [classesData, teachersData] = await Promise.all([
        apiGet<Class[]>('/classes/'),
        apiGet<User[]>('/users/?role=teacher'),
      ]);
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
        section: formData.section || undefined,
        session: formData.session,
        teacher_ids: formData.teacher_ids,
        class_teacher_id: formData.class_teacher_id || undefined,
      };

      if (editingClass) {
        await apiPatch<Class>(`/classes/${editingClass.id}/`, payload);
      } else {
        await apiPost<Class>('/classes/', payload);
      }

      setShowModal(false);
      setEditingClass(null);
      setFormData({ name: '', section: '', session: '', teacher_ids: [], class_teacher_id: '' });
      loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to save class');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (cls: Class) => {
    setEditingClass(cls);
    setFormData({
      name: cls.name,
      section: cls.section || '',
      session: cls.session || '',
      teacher_ids: cls.teacher_ids,
      class_teacher_id: cls.class_teacher_id || '',
    });
    setShowModal(true);
  };

  const handleDelete = async (classId: string) => {
    if (!confirm('Are you sure you want to delete this class?')) return;

    try {
      await apiDelete(`/classes/${classId}/`);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete class');
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
        <h1 className="text-xl">Classes</h1>
        <button
          className="btn btn-primary"
          onClick={() => {
            setEditingClass(null);
            setFormData({ name: '', section: '', session: '', teacher_ids: [], class_teacher_id: '' });
            setShowModal(true);
          }}
        >
          Create Class
        </button>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Section</th>
                <th>Session</th>
                <th>Teachers</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((cls) => (
                <tr key={cls.id}>
                  <td style={{ fontWeight: 500 }}>{cls.name}</td>
                  <td>{cls.section || '-'}</td>
                  <td>
                    <span className="node node-purple">{cls.session}</span>
                  </td>
                  <td>
                    {cls.teacher_ids.length > 0 ? (
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        {cls.teacher_ids.map(tid => {
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
                      onClick={() => handleEdit(cls)}
                    >
                      Edit
                    </button>
                    {user?.role === 'admin' && (
                      <button
                        className="btn"
                        style={{ color: 'var(--error)' }}
                        onClick={() => handleDelete(cls.id)}
                      >
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {classes.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                    No classes found
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
            <h2>{editingClass ? 'Edit Class' : 'Create Class'}</h2>
            {formError && <div className="error-message">{formError}</div>}
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Class Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Section (optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.section}
                  onChange={(e) => setFormData({ ...formData, section: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Session <span style={{ color: 'var(--error)' }}>*</span></label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.session}
                  onChange={(e) => setFormData({ ...formData, session: e.target.value })}
                  placeholder="e.g., 2025-26"
                  required
                />
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
              <div className="form-group">
                <label className="form-label">Class Teacher</label>
                <select
                  className="form-input"
                  value={formData.class_teacher_id}
                  onChange={(e) => setFormData({ ...formData, class_teacher_id: e.target.value })}
                >
                  <option value="">Select class teacher</option>
                  {teachers
                    .filter(t => formData.teacher_ids.includes(t.id))
                    .map(teacher => (
                      <option key={teacher.id} value={teacher.id}>{teacher.full_name}</option>
                    ))}
                </select>
              </div>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : editingClass ? 'Update' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
