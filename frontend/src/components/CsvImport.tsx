"use client";

import { useState, useCallback } from 'react';
import { uploadFile } from '@/lib/api';

interface CsvImportProps {
  onSuccess: () => void;
  onClose: () => void;
}

interface PreviewRow {
  email: string;
  full_name: string;
  role: string;
  class_id?: string;
  roll_no?: string;
}

export default function CsvImport({ onSuccess, onClose }: CsvImportProps) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewRow[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    success_count: number;
    error_count: number;
    errors: string[];
  } | null>(null);

  const handleFileSelect = useCallback(async (selectedFile: File) => {
    if (!selectedFile.name.endsWith('.csv')) {
      setError('Please select a CSV file');
      return;
    }

    setFile(selectedFile);
    setError(null);
    setResult(null);

    // Read and preview CSV
    const text = await selectedFile.text();
    const lines = text.split('\n').filter(line => line.trim());
    const headers = lines[0].split(',').map(h => h.trim());

    const previewData: PreviewRow[] = lines.slice(1, 6).map(line => {
      const values = line.split(',').map(v => v.trim());
      return {
        email: values[headers.indexOf('email')] || '',
        full_name: values[headers.indexOf('full_name')] || '',
        role: values[headers.indexOf('role')] || 'student',
        class_id: values[headers.indexOf('class_id')] || '',
        roll_no: values[headers.indexOf('roll_no')] || '',
      };
    });

    setPreview(previewData);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      handleFileSelect(droppedFile);
    }
  }, [handleFileSelect]);

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await uploadFile('/users/import', formData);
      const resultData = {
        success_count: (response.success_count as number) || 0,
        error_count: (response.error_count as number) || 0,
        errors: (response.errors as string[]) || [],
      };
      setResult(resultData);

      if (resultData.success_count > 0) {
        onSuccess();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDownloadSample = () => {
    const csvContent = "email,full_name,password,class_id,roll_no\njohn.doe@school.edu,John Doe,student123,,01\njane.smith@school.edu,Jane Smith,student123,,02\n";
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'student_import_template.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      {error && <div className="error-message" style={{ marginBottom: '1rem' }}>{error}</div>}

      {result ? (
        <div>
          <div style={{ padding: '1rem', backgroundColor: 'var(--success)', color: 'white', borderRadius: '8px', marginBottom: '1rem' }}>
            Successfully imported {result.success_count} students
            {result.error_count > 0 && ` with ${result.error_count} errors`}
          </div>
          {result.errors.length > 0 && (
            <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '1rem' }}>
              <h3>Errors:</h3>
              <ul>
                {result.errors.map((err, idx) => (
                  <li key={idx} style={{ color: 'var(--error)', fontSize: '0.875rem' }}>{err}</li>
                ))}
              </ul>
            </div>
          )}
          <button className="btn btn-primary" onClick={onClose}>Close</button>
        </div>
      ) : (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Need a starting template? You can leave <code>class_id</code> empty or use a Class Name like &quot;10-A&quot;.
            </span>
            <button
              className="btn btn-secondary"
              onClick={handleDownloadSample}
              style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
            >
              📥 Download Sample CSV
            </button>
          </div>

          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={handleDrop}
            style={{
              border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--border-default)'}`,
              borderRadius: '8px',
              padding: '2rem',
              textAlign: 'center',
              marginBottom: '1rem',
              backgroundColor: dragging ? 'var(--accent-glow)' : 'transparent',
              cursor: 'pointer',
            }}
            onClick={() => {
              const input = document.createElement('input');
              input.type = 'file';
              input.accept = '.csv';
              input.onchange = (e) => {
                const target = e.target as HTMLInputElement;
                if (target.files?.[0]) {
                  handleFileSelect(target.files[0]);
                }
              };
              input.click();
            }}
          >
            <p style={{ marginBottom: '0.5rem', color: dragging ? 'var(--accent)' : 'var(--text-secondary)' }}>
              {dragging ? 'Drop CSV file here' : 'Drag & drop CSV file or click to select'}
            </p>
            {file && <p style={{ fontSize: '0.875rem' }}>Selected: {file.name}</p>}
          </div>

          {preview.length > 0 && (
            <div style={{ marginBottom: '1rem' }}>
              <h3>Preview (first 5 rows):</h3>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-default)' }}>
                    <th style={{ padding: '0.5rem', textAlign: 'left' }}>Email</th>
                    <th style={{ padding: '0.5rem', textAlign: 'left' }}>Name</th>
                    <th style={{ padding: '0.5rem', textAlign: 'left' }}>Role</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid var(--border-default)' }}>
                      <td style={{ padding: '0.5rem' }}>{row.email}</td>
                      <td style={{ padding: '0.5rem' }}>{row.full_name}</td>
                      <td style={{ padding: '0.5rem' }}>{row.role}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
            <button className="btn btn-secondary" onClick={onClose} disabled={uploading}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              onClick={handleUpload}
              disabled={!file || uploading}
            >
              {uploading ? 'Uploading...' : 'Upload & Import'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
