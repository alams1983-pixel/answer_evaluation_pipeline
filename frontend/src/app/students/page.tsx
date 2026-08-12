"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete, uploadFile } from '@/lib/api';
import CsvImport from '@/components/CsvImport';

interface Student {
  id: string;
  email: string;
  full_name: string;
  role: 'student';
  class_id: string | null;
  roll_no: string | null;
  is_active: boolean;
  created_at: string;
}

interface Class {
  id: string;
  name: string;
  section: string | null;
}

export default function StudentsPage() {
  const { user, loading: authLoading } = useAuth();
  const [students, setStudents] = useState<Student[]>([]);
  const [classes, setClasses] = useState<Class[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [classFilter, setClassFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showImportModal, setShowImportModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingStudent, setEditingStudent] = useState<Student | null>(null);

  const [formData, setFormData] = useState({
    email: '',
    full_name: '',
    password: '',
    class_id: '',
    roll_no: '',
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
      const [studentsData, classesData] = await Promise.all([
        apiGet<Student[]>('/students/'),
        apiGet<Class[]>('/classes/'),
      ]);
      setStudents(studentsData);
      setClasses(classesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);

    try {
      await apiPost<Student>('/students/', {
        email: formData.email,
        full_name: formData.full_name,
        password: formData.password,
        role: 'student',
        class_id: formData.class_id || undefined,
        roll_no: formData.roll_no || undefined,
      });

      setShowCreateModal(false);
      setFormData({ email: '', full_name: '', password: '', class_id: '', roll_no: '' });
      loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to create student');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingStudent) return;
    setFormError(null);
    setSubmitting(true);

    try {
      const updateData: Record<string, unknown> = {
        full_name: formData.full_name,
        class_id: formData.class_id || undefined,
        roll_no: formData.roll_no || undefined,
        is_active: editingStudent.is_active,
      };
      if (formData.password) {
        updateData.password = formData.password;
      }

      await apiPatch<Student>(`/students/${editingStudent.id}/`, updateData);

      setShowEditModal(false);
      setEditingStudent(null);
      setFormData({ email: '', full_name: '', password: '', class_id: '', roll_no: '' });
      loadData();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Failed to update student');
    } finally {
      setSubmitting(false);
    }
  };

  const openEditModal = (student: Student) => {
    setEditingStudent(student);
    setFormData({
      email: student.email,
      full_name: student.full_name,
      password: '',
      class_id: student.class_id || '',
      roll_no: student.roll_no || '',
    });
    setShowEditModal(true);
  };

  const handleToggleActive = async (studentId: string, currentActive: boolean) => {
    try {
      await apiPatch<Student>(`/students/${studentId}/`, { is_active: !currentActive });
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update student');
    }
  };

  const handleDelete = async (studentId: string) => {
    if (!confirm('Are you sure you want to delete this student?')) return;
    try {
      await apiDelete(`/students/${studentId}/`);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete student');
    }
  };

  const downloadSampleCsv = () => {
    const sampleCsv = 'email,full_name,password,class_id,roll_no\njohn@example.com,John Doe,password123,CLASS_ID_HERE,01\njane@example.com,Jane Smith,password456,CLASS_ID_HERE,02\n';
    const blob = new Blob([sampleCsv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_students.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const filteredStudents = students.filter(student => {
    const matchesSearch = searchQuery === '' ||
      student.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      student.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (student.roll_no && student.roll_no.includes(searchQuery));

    const matchesClass = classFilter === 'all' || student.class_id === classFilter;
    const matchesStatus = statusFilter === 'all' ||
      (statusFilter === 'active' && student.is_active) ||
      (statusFilter === 'inactive' && !student.is_active);

    return matchesSearch && matchesClass && matchesStatus;
  });

  const getClassLabel = (classId: string | null) => {
    if (!classId) return '-';
    const cls = classes.find(c => c.id === classId);
    return cls ? `${cls.name}${cls.section ? ` - ${cls.section}` : ''}` : '-';
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
        <div className="section-header" style={{ marginBottom: 0 }}>
          <h1 className="text-xl">Students</h1>
          <span className="section-badge">{filteredStudents.length} students</span>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-secondary" onClick={downloadSampleCsv}>
            Download Sample CSV
          </button>
          <button className="btn btn-secondary" onClick={() => setShowImportModal(true)}>
            Import CSV
          </button>
          <button className="btn btn-primary" onClick={() => {
            setFormData({ email: '', full_name: '', password: '', class_id: '', roll_no: '' });
            setShowCreateModal(true);
          }}>
            Add Student
          </button>
        </div>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div className="panel" style={{ padding: '1rem', marginBottom: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <label className="form-label">Search</label>
          <input
            type="text"
            className="form-input"
            placeholder="Name, email, or roll no..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div style={{ minWidth: '180px' }}>
          <label className="form-label">Class</label>
          <select
            value={classFilter}
            onChange={(e) => setClassFilter(e.target.value)}
            className="form-input"
          >
            <option value="all">All Classes</option>
            {classes.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.section ? ` - ${c.section}` : ''}</option>
            ))}
          </select>
        </div>
        <div style={{ minWidth: '150px' }}>
          <label className="form-label">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="form-input"
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>
      ) : (
        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Roll No</th>
                <th>Class</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredStudents.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontWeight: 500 }}>{s.full_name}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{s.email}</td>
                  <td>
                    {s.roll_no ? (
                      <span className="node node-blue">{s.roll_no}</span>
                    ) : '-'}
                  </td>
                  <td>{getClassLabel(s.class_id)}</td>
                  <td>
                    <span className={`status-badge ${s.is_active ? 's-graded' : 's-failed'}`}>
                      {s.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button className="btn btn-secondary" onClick={() => openEditModal(s)}>
                      Edit
                    </button>
                    <button className="btn btn-secondary" onClick={() => handleToggleActive(s.id, s.is_active)}>
                      {s.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    {user?.role === 'admin' && (
                      <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDelete(s.id)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {filteredStudents.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', color: 'var(--text-secondary)' }}>
                    {students.length === 0 ? 'No students found. Add students or import from CSV.' : 'No students match the current filters.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Add Student</h2>
            {formError && <div className="error-message">{formError}</div>}
            <form onSubmit={handleCreateStudent}>
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Email</label>
                <input
                  type="email"
                  className="form-input"
                  value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">Class</label>
                <select
                  className="form-input"
                  value={formData.class_id}
                  onChange={(e) => setFormData({ ...formData, class_id: e.target.value })}
                >
                  <option value="">Select class</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}{c.section ? ` - ${c.section}` : ''}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Roll No</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.roll_no}
                  onChange={(e) => setFormData({ ...formData, roll_no: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowCreateModal(false)}>
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

      {showEditModal && editingStudent && (
        <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Edit Student</h2>
            {formError && <div className="error-message">{formError}</div>}
            <form onSubmit={handleEditStudent}>
              <div className="form-group">
                <label className="form-label">Email (read-only)</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.email}
                  disabled
                  style={{ opacity: 0.6, cursor: 'not-allowed' }}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Full Name</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label">New Password (leave blank to keep current)</label>
                <input
                  type="password"
                  className="form-input"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="Leave blank to keep current password"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Class</label>
                <select
                  className="form-input"
                  value={formData.class_id}
                  onChange={(e) => setFormData({ ...formData, class_id: e.target.value })}
                >
                  <option value="">No class assigned</option>
                  {classes.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}{c.section ? ` - ${c.section}` : ''}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Roll No</label>
                <input
                  type="text"
                  className="form-input"
                  value={formData.roll_no}
                  onChange={(e) => setFormData({ ...formData, roll_no: e.target.value })}
                />
              </div>
              <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                <button type="button" className="btn btn-secondary" onClick={() => {
                  setShowEditModal(false);
                  setEditingStudent(null);
                }}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showImportModal && (
        <div className="modal-overlay" onClick={() => setShowImportModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h2 style={{ margin: 0 }}>Import Students from CSV</h2>
              <button className="btn btn-secondary" onClick={downloadSampleCsv}>
                Download Sample
              </button>
            </div>
            <CsvImport
              onSuccess={() => {
                setShowImportModal(false);
                loadData();
              }}
              onClose={() => setShowImportModal(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
