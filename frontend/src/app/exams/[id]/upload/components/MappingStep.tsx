"use client";

import { useState, useEffect, useCallback } from 'react';
import PageThumbnail from './PageThumbnail';
import ZoomModal from './ZoomModal';
import SavedRecordsList from './SavedRecordsList';
import StudentLookupDropdown from '@/components/StudentLookupDropdown';
import {
  AnswerSheet,
  SheetPage,
  StudentDropdownItem,
  getSheetsForExam,
  getSheetPages,
  updateSheetMapping,
  deleteSheetPage,
  skipSheet,
  getPageImageUrl,
  deleteAllPendingSheets,
  getAutoMatchSuggestions,
  applyAutoMatch,
  AutoMatchSuggestion,
} from '@/lib/api';

interface MappingStepProps {
  examId: string;
  onComplete: () => void;
}

export default function MappingStep({ examId, onComplete }: MappingStepProps) {
  const [pendingSheets, setPendingSheets] = useState<AnswerSheet[]>([]);
  const [savedSheets, setSavedSheets] = useState<AnswerSheet[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [pages, setPages] = useState<SheetPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);

  const [studentName, setStudentName] = useState('');
  const [rollNo, setRollNo] = useState('');
  const [classLabel, setClassLabel] = useState('');
  const [selectedStudent, setSelectedStudent] = useState<StudentDropdownItem | null>(null);

  const [zoomSrc, setZoomSrc] = useState<string | null>(null);

  const [showAutoMatch, setShowAutoMatch] = useState(false);
  const [autoMatchSuggestions, setAutoMatchSuggestions] = useState<AutoMatchSuggestion[]>([]);
  const [autoMatchLoading, setAutoMatchLoading] = useState(false);
  const [autoMatchApplying, setAutoMatchApplying] = useState(false);
  const [selectedMatches, setSelectedMatches] = useState<Set<string>>(new Set());
  const [autoMatchError, setAutoMatchError] = useState<string | null>(null);
  const [autoMatchSuccess, setAutoMatchSuccess] = useState<string | null>(null);

  const loadPendingSheets = useCallback(async () => {
    try {
      const pending = await getSheetsForExam(examId, 'pending_mapping');
      setPendingSheets(pending);

      const mapped = await getSheetsForExam(examId, 'mapped');
      setSavedSheets(mapped);

      if (pending.length === 0) {
        setLoading(false);
        return;
      }

      const first = pending[0];
      setCurrentIndex(0);
      setStudentName(first.student_name || '');
      setRollNo(first.roll_no || '');
      setClassLabel(first.class_label || '');
      setSelectedStudent(null);

      const sheetPages = await getSheetPages(first.id);
      setPages(sheetPages);
    } catch (err) {
      console.error('Failed to load sheets:', err);
    } finally {
      setLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    loadPendingSheets();
  }, [loadPendingSheets]);

  const loadCurrentSheetPages = async (sheet: AnswerSheet) => {
    const sheetPages = await getSheetPages(sheet.id);
    setPages(sheetPages);
  };

  const handleSaveAndNext = async () => {
    if (!pendingSheets[currentIndex]) return;
    setSaving(true);
    try {
      const sheet = pendingSheets[currentIndex];
      await updateSheetMapping(sheet.id, {
        student_name: studentName || undefined,
        roll_no: rollNo || undefined,
        class_label: classLabel || undefined,
        student_id: selectedStudent?.id,
      });

      setSavedSheets((prev) => [...prev, { ...sheet, status: 'mapped' }]);

      const updatedPending = pendingSheets.filter((s) => s.id !== sheet.id);
      setPendingSheets(updatedPending);

      if (updatedPending.length === 0) {
        await loadPendingSheets();
        if (pendingSheets.length <= 1) {
          onComplete();
        }
      } else {
        const newIndex = currentIndex >= updatedPending.length ? updatedPending.length - 1 : currentIndex;
        setCurrentIndex(newIndex);
        const nextSheet = updatedPending[newIndex];
        setStudentName(nextSheet.student_name || '');
        setRollNo(nextSheet.roll_no || '');
        setClassLabel(nextSheet.class_label || '');
        setSelectedStudent(null);
        await loadCurrentSheetPages(nextSheet);
      }
    } catch (err) {
      console.error('Failed to save mapping:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleStudentSelect = (student: StudentDropdownItem | null) => {
    setSelectedStudent(student);
    if (student) {
      setStudentName(student.full_name);
      if (student.roll_no) setRollNo(student.roll_no);
    }
  };

  const handleOpenAutoMatch = async () => {
    try {
      setAutoMatchLoading(true);
      setAutoMatchError(null);
      const result = await getAutoMatchSuggestions(examId);
      setAutoMatchSuggestions(result.suggestions);
      setSelectedMatches(new Set(result.suggestions.map((s) => s.sheet_id)));
      setShowAutoMatch(true);
    } catch (err) {
      setAutoMatchError(err instanceof Error ? err.message : 'Failed to load suggestions');
    } finally {
      setAutoMatchLoading(false);
    }
  };

  const handleApplyAutoMatch = async () => {
    if (selectedMatches.size === 0) return;
    try {
      setAutoMatchApplying(true);
      const matchesToApply = autoMatchSuggestions
        .filter((s) => selectedMatches.has(s.sheet_id))
        .map((s) => ({
          sheet_id: s.sheet_id,
          student_id: s.matched_student.student_id,
          keep_parsed_name: false,
        }));
      const result = await applyAutoMatch(examId, { matches: matchesToApply });
      setAutoMatchSuccess(`Matched ${result.matched_count} sheets (${result.failed_count} failed)`);
      setShowAutoMatch(false);
      await loadPendingSheets();
    } catch (err) {
      setAutoMatchError(err instanceof Error ? err.message : 'Failed to apply matches');
    } finally {
      setAutoMatchApplying(false);
    }
  };

  const toggleMatchSelection = (sheetId: string) => {
    setSelectedMatches((prev) => {
      const next = new Set(prev);
      if (next.has(sheetId)) {
        next.delete(sheetId);
      } else {
        next.add(sheetId);
      }
      return next;
    });
  };

  const selectAllMatches = () => {
    setSelectedMatches(new Set(autoMatchSuggestions.map((s) => s.sheet_id)));
  };

  const deselectAllMatches = () => {
    setSelectedMatches(new Set());
  };

  const handleSkip = async () => {
    if (!pendingSheets[currentIndex]) return;
    if (!confirm('Skip this PDF without saving?')) return;

    setSaving(true);
    try {
      const sheet = pendingSheets[currentIndex];
      await skipSheet(sheet.id);

      const nextIndex = currentIndex + 1;
      if (nextIndex < pendingSheets.length) {
        setCurrentIndex(nextIndex);
        const nextSheet = pendingSheets[nextIndex];
        setStudentName(nextSheet.student_name || '');
        setRollNo(nextSheet.roll_no || '');
        setClassLabel(nextSheet.class_label || '');
        await loadCurrentSheetPages(nextSheet);
      } else {
        await loadPendingSheets();
      }
    } catch (err) {
      console.error('Failed to skip sheet:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePage = async (pageNo: number) => {
    if (!pendingSheets[currentIndex]) return;
    try {
      await deleteSheetPage(pendingSheets[currentIndex].id, pageNo);
      setPages((prev) => prev.filter((p) => p.page_no !== pageNo));
    } catch (err) {
      console.error('Failed to delete page:', err);
    }
  };

  const handleEditSaved = async (sheet: AnswerSheet) => {
    const idx = pendingSheets.findIndex((s) => s.id === sheet.id);
    if (idx !== -1) {
      setCurrentIndex(idx);
      setStudentName(sheet.student_name || '');
      setRollNo(sheet.roll_no || '');
      setClassLabel(sheet.class_label || '');
      await loadCurrentSheetPages(sheet);
    } else {
      setSavedSheets((prev) => prev.filter((s) => s.id !== sheet.id));
      setPendingSheets((prev) => [...prev, sheet]);
      const newIdx = pendingSheets.length;
      setCurrentIndex(newIdx);
      setStudentName(sheet.student_name || '');
      setRollNo(sheet.roll_no || '');
      setClassLabel(sheet.class_label || '');
      await loadCurrentSheetPages(sheet);
    }
  };

  const handleDeleteSaved = async (sheetId: string) => {
    setSavedSheets((prev) => prev.filter((s) => s.id !== sheetId));
  };

  const handleRemoveAllPending = async () => {
    if (!confirm(`Remove all ${pendingSheets.length} unmapped sheets? This will delete the PDFs and page images permanently.`)) return;
    setRemoving(true);
    try {
      await deleteAllPendingSheets(examId);
      setPendingSheets([]);
      setPages([]);
      setStudentName('');
      setRollNo('');
      setClassLabel('');
      setCurrentIndex(0);
      await loadPendingSheets();
    } catch (err) {
      console.error('Failed to remove pending sheets:', err);
      alert(err instanceof Error ? err.message : 'Failed to remove pending sheets');
    } finally {
      setRemoving(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>Loading sheets...</div>;
  }

  if (pendingSheets.length === 0 && savedSheets.length === 0) {
    return (
      <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
        No pending sheets to map. Upload a ZIP file first.
      </div>
    );
  }

  if (pendingSheets.length === 0 && savedSheets.length > 0) {
    return (
      <div>
        <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--success)', fontWeight: 600 }}>
          All PDFs processed
        </div>
        <SavedRecordsList
          sheets={savedSheets}
          onEdit={handleEditSaved}
          onDelete={handleDeleteSaved}
        />
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button className="btn btn-primary" onClick={onComplete}>
            Continue to Summary
          </button>
        </div>
      </div>
    );
  }

  const currentSheet = pendingSheets[currentIndex];
  const activePages = pages.filter((p) => !p.is_deleted);

  return (
    <div>
      <div className="mapping-header">
        <div className="mapping-counter">
          Process PDF <span className="current">{currentIndex + 1}</span> /{' '}
          <span className="total">{pendingSheets.length}</span>
          {currentSheet && (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginLeft: '0.75rem' }}>
              {currentSheet.original_filename}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            className="btn btn-secondary"
            onClick={handleOpenAutoMatch}
            disabled={autoMatchLoading}
            title="Auto-match sheets to enrolled students"
          >
            {autoMatchLoading ? 'Loading...' : 'Auto-Match'}
          </button>
          <button
            className="btn btn-secondary"
            style={{ color: 'var(--error)', border: '1px solid var(--error)' }}
            onClick={handleRemoveAllPending}
            disabled={removing}
            title="Remove all pending unmapped sheets"
          >
            {removing ? 'Removing...' : `Remove All Pending (${pendingSheets.length})`}
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleSkip}
            disabled={saving}
          >
            Skip
          </button>
        </div>
      </div>

      <div className="panel" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label className="form-label">Link to Enrolled Student</label>
          <StudentLookupDropdown
            examId={examId}
            value={selectedStudent?.id || ''}
            onChange={handleStudentSelect}
          />
        </div>

        <div className="mapping-form-grid">
          <div>
            <label className="form-label">Student Name</label>
            <input
              type="text"
              className="form-input"
              value={studentName}
              onChange={(e) => {
                setStudentName(e.target.value);
                setSelectedStudent(null);
              }}
              placeholder="Student name"
            />
          </div>
          <div>
            <label className="form-label">Roll No.</label>
            <input
              type="text"
              className="form-input"
              value={rollNo}
              onChange={(e) => {
                setRollNo(e.target.value);
                setSelectedStudent(null);
              }}
              placeholder="Roll"
            />
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <label className="form-label">Class</label>
            <input
              type="text"
              className="form-input"
              value={classLabel}
              onChange={(e) => setClassLabel(e.target.value)}
              placeholder="Class / Section"
            />
          </div>
        </div>

        <div style={{ marginTop: '1rem' }}>
          <label className="form-label">Answer Sheet Pages</label>
          {activePages.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem', fontSize: '0.875rem' }}>
              No pages remaining. All pages have been deleted.
            </div>
          ) : (
            <div className="page-thumbnails">
              {activePages.map((page) => (
                <PageThumbnail
                  key={page.page_no}
                  sheetId={currentSheet.id}
                  pageNo={page.page_no}
                  onZoom={() => setZoomSrc(getPageImageUrl(currentSheet.id, page.page_no))}
                  onDelete={() => handleDeletePage(page.page_no)}
                />
              ))}
            </div>
          )}
        </div>

        <div style={{ marginTop: '1.25rem' }}>
          <button
            className="btn btn-primary"
            style={{ width: '100%' }}
            onClick={handleSaveAndNext}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save & Next'}
          </button>
        </div>
      </div>

      {savedSheets.length > 0 && (
        <SavedRecordsList
          sheets={savedSheets}
          onEdit={handleEditSaved}
          onDelete={handleDeleteSaved}
        />
      )}

      {zoomSrc && <ZoomModal src={zoomSrc} onClose={() => setZoomSrc(null)} />}

      {showAutoMatch && (
        <div className="modal-overlay" onClick={() => setShowAutoMatch(false)}>
          <div className="modal-content" style={{ maxWidth: '800px', maxHeight: '80vh', overflow: 'auto' }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
              <h2 style={{ marginBottom: 0 }}>Auto-Match Sheets to Students</h2>
              <button onClick={() => setShowAutoMatch(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '1.5rem', cursor: 'pointer' }}>&times;</button>
            </div>

            {autoMatchError && (
              <div className="error-message" style={{ marginBottom: '1rem' }}>
                {autoMatchError}
                <button onClick={() => setAutoMatchError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
              </div>
            )}

            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
              <button className="btn btn-secondary" onClick={selectAllMatches}>Select All</button>
              <button className="btn btn-secondary" onClick={deselectAllMatches}>Deselect All</button>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem', marginLeft: '0.5rem' }}>
                {selectedMatches.size} of {autoMatchSuggestions.length} selected
              </span>
            </div>

            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>✓</th>
                    <th>PDF Filename</th>
                    <th>Parsed Name</th>
                    <th>Parsed Roll</th>
                    <th>Matched Student</th>
                    <th>Student Roll</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {autoMatchSuggestions.map((suggestion) => {
                    const confidenceColor =
                      suggestion.confidence >= 0.8 ? 'var(--success)' :
                      suggestion.confidence >= 0.5 ? 'var(--warning)' : 'var(--error)';
                    return (
                      <tr key={suggestion.sheet_id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedMatches.has(suggestion.sheet_id)}
                            onChange={() => toggleMatchSelection(suggestion.sheet_id)}
                          />
                        </td>
                        <td style={{ fontSize: '0.8rem' }}>{suggestion.original_filename}</td>
                        <td>{suggestion.parsed_name || '-'}</td>
                        <td>{suggestion.parsed_roll || '-'}</td>
                        <td style={{ fontWeight: 500 }}>{suggestion.matched_student.full_name}</td>
                        <td>{suggestion.matched_student.roll_no || '-'}</td>
                        <td>
                          <span style={{ fontWeight: 700, color: confidenceColor }}>
                            {Math.round(suggestion.confidence * 100)}%
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {autoMatchSuggestions.length === 0 && (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                No matches found. Sheets without matching students will remain pending.
              </div>
            )}

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end', marginTop: '1.5rem' }}>
              <button className="btn btn-secondary" onClick={() => setShowAutoMatch(false)}>
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleApplyAutoMatch}
                disabled={autoMatchApplying || selectedMatches.size === 0}
              >
                {autoMatchApplying ? 'Applying...' : `Apply ${selectedMatches.size} Matches`}
              </button>
            </div>
          </div>
        </div>
      )}

      {autoMatchSuccess && (
        <div style={{ textAlign: 'center', padding: '0.75rem', background: 'var(--success-bg)', borderRadius: 'var(--radius-md)', color: 'var(--success-text)', marginBottom: '1rem' }}>
          {autoMatchSuccess}
          <button onClick={() => setAutoMatchSuccess(null)} style={{ marginLeft: '1rem', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}
    </div>
  );
}
