'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  getExamStudents,
  getExamStudentsSummary,
  syncExamStudents,
  ExamStudentsSummary,
} from '@/lib/api';

interface StudentWithSheetStatus {
  id: string;
  email: string;
  full_name: string;
  role: string;
  class_id: string | null;
  roll_no: string | null;
  is_active: boolean;
  enrollment_status: 'active' | 'removed';
  enrolled_at: string;
  removed_at: string | null;
  sheet_status?: string;
  sheet_id?: string | null;
  sheet_filename?: string | null;
}

interface StudentsTabProps {
  examId: string;
}

export default function StudentsTab({ examId }: StudentsTabProps) {
  const [students, setStudents] = useState<StudentWithSheetStatus[]>([]);
  const [summary, setSummary] = useState<ExamStudentsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [studentsData, summaryData] = await Promise.all([
        getExamStudents(examId),
        getExamStudentsSummary(examId),
      ]);
      setStudents(studentsData);
      setSummary(summaryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load students');
    } finally {
      setLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSync = async () => {
    try {
      setSyncing(true);
      const result = await syncExamStudents(examId);
      setSuccess(
        `Synced: ${result.added_count} added, ${result.removed_count} removed. ${result.total_active} active students.`,
      );
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to sync students');
    } finally {
      setSyncing(false);
    }
  };

  const filteredStudents = students.filter((s) => {
    if (statusFilter === 'all') return true;
    return s.enrollment_status === statusFilter;
  });

  const getMappingStatusBadge = (s: StudentWithSheetStatus) => {
    if (s.enrollment_status === 'removed') {
      return <span className="node node-red">Removed</span>;
    }

    const sheetStatus = s.sheet_status || 'no_sheet';

    if (sheetStatus === 'no_sheet') {
      return <span className="node node-red">No Sheet Uploaded</span>;
    }
    if (sheetStatus === 'pending_mapping') {
      return <span className="node node-yellow">Pending Mapping</span>;
    }
    if (sheetStatus === 'mapped') {
      return <span className="node node-blue">Mapped</span>;
    }
    if (sheetStatus === 'graded') {
      return <span className="node node-purple">Graded</span>;
    }
    if (sheetStatus === 'reviewed') {
      return <span className="node node-teal">Reviewed</span>;
    }
    if (sheetStatus === 'published') {
      return <span className="node node-green">Published</span>;
    }
    if (sheetStatus === 'skipped') {
      return <span className="node node-orange">Skipped</span>;
    }
    return <span style={{ color: 'var(--text-muted)' }}>{sheetStatus}</span>;
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading enrolled students...</div>;
  }

  return (
    <div>
      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>
            &times;
          </button>
        </div>
      )}

      {success && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--success-bg)', border: '1px solid var(--success)', borderRadius: 'var(--radius-md)', color: 'var(--success-text)', fontSize: '0.875rem' }}>
          {success}
          <button onClick={() => setSuccess(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>
            &times;
          </button>
        </div>
      )}

      {summary && (
        <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
              <div style={{ textAlign: 'center' }}>
                <div className="node node-green" style={{ fontSize: '1.25rem', fontWeight: 700, padding: '0.5rem 1rem' }}>
                  {summary.active_students}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Active</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="node node-red" style={{ fontSize: '1.25rem', fontWeight: 700, padding: '0.5rem 1rem' }}>
                  {summary.removed_students}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Removed</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="node node-blue" style={{ fontSize: '1.25rem', fontWeight: 700, padding: '0.5rem 1rem' }}>
                  {summary.mapped_sheets}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Mapped Sheets</div>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div className="node node-orange" style={{ fontSize: '1.25rem', fontWeight: 700, padding: '0.5rem 1rem' }}>
                  {summary.unmapped_sheets}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>Unmapped Sheets</div>
              </div>
            </div>
            <button className="btn btn-primary" onClick={handleSync} disabled={syncing}>
              {syncing ? 'Syncing...' : 'Sync Students'}
            </button>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
        <button
          className={statusFilter === 'all' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setStatusFilter('all')}
        >
          All
        </button>
        <button
          className={statusFilter === 'active' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setStatusFilter('active')}
        >
          Active
        </button>
        <button
          className={statusFilter === 'removed' ? 'btn btn-primary' : 'btn btn-secondary'}
          onClick={() => setStatusFilter('removed')}
        >
          Removed
        </button>
      </div>

      <div className="panel" style={{ padding: '1rem' }}>
        {filteredStudents.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center' }}>
            No students found. Click "Sync Students" to populate from the exam's class.
          </p>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Roll No</th>
                  <th>Enrollment</th>
                  <th>Mapping Status</th>
                  <th>Enrolled</th>
                </tr>
              </thead>
              <tbody>
                {filteredStudents.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 500 }}>{s.full_name}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{s.roll_no || '-'}</td>
                    <td>
                      <span className={`node node-${s.enrollment_status === 'active' ? 'green' : 'red'}`}>
                        {s.enrollment_status}
                      </span>
                    </td>
                    <td>{getMappingStatusBadge(s)}</td>
                    <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {new Date(s.enrolled_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
