"use client";

import { useState, useEffect } from 'react';
import { getSheetsForExam, AnswerSheet } from '@/lib/api';
import SavedRecordsList from './SavedRecordsList';
import Link from 'next/link';

interface DoneStepProps {
  examId: string;
  onBackToMapping: () => void;
}

export default function DoneStep({ examId, onBackToMapping }: DoneStepProps) {
  const [mappedSheets, setMappedSheets] = useState<AnswerSheet[]>([]);
  const [skippedSheets, setSkippedSheets] = useState<AnswerSheet[]>([]);
  const [pendingSheets, setPendingSheets] = useState<AnswerSheet[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAll = async () => {
      try {
        const [mapped, skipped, pending] = await Promise.all([
          getSheetsForExam(examId, 'mapped'),
          getSheetsForExam(examId, 'skipped'),
          getSheetsForExam(examId, 'pending_mapping'),
        ]);
        setMappedSheets(mapped);
        setSkippedSheets(skipped);
        setPendingSheets(pending);
      } catch (err) {
        console.error('Failed to load sheets:', err);
      } finally {
        setLoading(false);
      }
    };
    loadAll();
  }, [examId]);

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>Loading summary...</div>;
  }

  const total = mappedSheets.length + skippedSheets.length + pendingSheets.length;

  return (
    <div>
      <div className="section-header">
        <h2 className="text-md" style={{ margin: 0, fontWeight: 600 }}>Upload Complete</h2>
        <span className="section-badge">SUMMARY</span>
      </div>

      <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', textAlign: 'center' }}>
          <div>
            <div className="text-2xl" style={{ fontWeight: 700 }}>{total}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Total PDFs</div>
          </div>
          <div>
            <div className="text-2xl" style={{ fontWeight: 700, color: 'var(--success)' }}>{mappedSheets.length}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Mapped</div>
          </div>
          <div>
            <div className="text-2xl" style={{ fontWeight: 700, color: 'var(--warning)' }}>{skippedSheets.length}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Skipped</div>
          </div>
          <div>
            <div className="text-2xl" style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>{pendingSheets.length}</div>
            <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>Pending</div>
          </div>
        </div>
      </div>

      {mappedSheets.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <SavedRecordsList
            sheets={mappedSheets}
            onEdit={() => {}}
            onDelete={() => {}}
          />
        </div>
      )}

      {skippedSheets.length > 0 && (
        <div className="panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
          <h3 className="text-sm" style={{ marginBottom: '0.75rem', fontWeight: 600, color: 'var(--warning)' }}>
            Skipped Sheets ({skippedSheets.length})
          </h3>
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Parsed Name</th>
                  <th>Roll</th>
                  <th>Class</th>
                </tr>
              </thead>
              <tbody>
                {skippedSheets.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{s.original_filename}</td>
                    <td>{s.student_name || '-'}</td>
                    <td>{s.roll_no || '-'}</td>
                    <td>{s.class_label || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '1.5rem' }}>
        {pendingSheets.length > 0 && (
          <button className="btn btn-secondary" onClick={onBackToMapping}>
            Continue Mapping
          </button>
        )}
        <Link href={`/exams/${examId}`} className="btn btn-primary">
          Back to Exam Details
        </Link>
      </div>
    </div>
  );
}
