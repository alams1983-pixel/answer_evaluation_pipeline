'use client';

import { useState, useEffect } from 'react';
import {
  getExamStudentsDropdown,
  StudentDropdownItem,
} from '@/lib/api';

interface StudentLookupDropdownProps {
  examId: string;
  value: string;
  onChange: (student: StudentDropdownItem | null) => void;
}

export default function StudentLookupDropdown({ examId, value, onChange }: StudentLookupDropdownProps) {
  const [students, setStudents] = useState<StudentDropdownItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStudents();
  }, [examId]);

  const loadStudents = async () => {
    try {
      setLoading(true);
      const data = await getExamStudentsDropdown(examId);
      setStudents(data);
    } catch (err) {
      setError('Failed to load students');
    } finally {
      setLoading(false);
    }
  };

  const selectedStudent = students.find(s => s.id === value);

  const filtered = search
    ? students.filter(s =>
        s.full_name.toLowerCase().includes(search.toLowerCase()) ||
        (s.roll_no && s.roll_no.toLowerCase().includes(search.toLowerCase())) ||
        s.email.toLowerCase().includes(search.toLowerCase()),
      )
    : students;

  return (
    <div style={{ position: 'relative' }}>
      <div
        onClick={() => setIsOpen(!isOpen)}
        style={{
          padding: '0.5rem 0.75rem',
          background: 'var(--bg-tertiary)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          minHeight: '38px',
        }}
      >
        {selectedStudent ? (
          <span>
            {selectedStudent.full_name}
            {selectedStudent.roll_no && (
              <span style={{ color: 'var(--text-muted)', marginLeft: '0.5rem' }}>
                (Roll: {selectedStudent.roll_no})
              </span>
            )}
          </span>
        ) : (
          <span style={{ color: 'var(--text-muted)' }}>Search or select a student...</span>
        )}
        <span style={{ marginLeft: '0.5rem', color: 'var(--text-muted)' }}>{isOpen ? '▲' : '▼'}</span>
      </div>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 1000,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            maxHeight: '300px',
            overflow: 'auto',
            marginTop: '0.25rem',
          }}
        >
          <div style={{ padding: '0.5rem' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Search by name, roll no, or email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onClick={(e) => e.stopPropagation()}
              style={{ width: '100%' }}
            />
          </div>

          {loading && (
            <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              Loading students...
            </div>
          )}

          {error && (
            <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--error)' }}>
              {error}
            </div>
          )}

          {!loading && !error && filtered.length === 0 && (
            <div style={{ padding: '1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              No students found
            </div>
          )}

          {filtered.map(student => (
            <div
              key={student.id}
              onClick={() => {
                onChange(student);
                setIsOpen(false);
                setSearch('');
              }}
              style={{
                padding: '0.5rem 1rem',
                cursor: 'pointer',
                background: student.id === value ? 'var(--accent)' : 'transparent',
                color: student.id === value ? 'white' : 'inherit',
                transition: 'background 0.15s',
              }}
              onMouseEnter={(e) => {
                if (student.id !== value) {
                  (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-tertiary)';
                }
              }}
              onMouseLeave={(e) => {
                if (student.id !== value) {
                  (e.currentTarget as HTMLDivElement).style.background = 'transparent';
                }
              }}
            >
              <div style={{ fontWeight: 500 }}>{student.full_name}</div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {student.roll_no ? `Roll: ${student.roll_no}` : 'No roll no'} • {student.email}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
