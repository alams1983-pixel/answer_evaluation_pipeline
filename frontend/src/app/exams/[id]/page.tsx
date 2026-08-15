"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet, apiPost, apiPatch, apiDelete, uploadFile, getSheetsForExam, deleteAllPendingSheets, Grading, publishAllGradings } from '@/lib/api';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import SchemaBuilder from '@/components/SchemaBuilder';
import { SchemaField, jsonSchemaToFields, fieldsToJsonSchema } from '@/lib/schema-builder';
import ZipUpload from '@/components/ZipUpload';
import QuestionPaperTab from '@/components/QuestionPaperTab';
import StudentsTab from '@/components/StudentsTab';

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

interface Question {
  q_no: string;
  question: string | null;
  expected_answer: string | null;
  marks: number;
  keywords: string[];
  marking_scheme: string | null;
}

interface SampleSheet {
  kind: string;
  path: string;
  label: string;
  notes: string | null;
}

interface ResultSchema {
  id: string;
  name: string;
  description: string | null;
  schema_definition: object;
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
}

type Tab = 'overview' | 'answer-key' | 'question-paper' | 'samples' | 'result-schema' | 'students' | 'upload-sheets' | 'batches' | 'results';

export default function ExamDetailPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const router = useRouter();
  const examId = params.id as string;

  const [exam, setExam] = useState<Exam | null>(null);
  const [classes, setClasses] = useState<Class[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [answerKey, setAnswerKey] = useState<{ id: string; questions: Question[]; sample_sheets: SampleSheet[] } | null>(null);
  const [samples, setSamples] = useState<SampleSheet[]>([]);
  const [resultSchema, setResultSchema] = useState<ResultSchema | null>(null);
  const [allSchemas, setAllSchemas] = useState<ResultSchema[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [pendingSheetsCount, setPendingSheetsCount] = useState(0);

  const [questions, setQuestions] = useState<Question[]>([]);
  const [editingQuestion, setEditingQuestion] = useState<number | null>(null);
  const [questionForm, setQuestionForm] = useState<Question>({
    q_no: '',
    question: null,
    expected_answer: null,
    marks: 0,
    keywords: [],
    marking_scheme: null,
  });

  const [sampleLabel, setSampleLabel] = useState('');
  const [sampleNotes, setSampleNotes] = useState('');
  const [uploadingSample, setUploadingSample] = useState(false);

  const [schemaName, setSchemaName] = useState('');
  const [schemaDescription, setSchemaDescription] = useState('');
  const [selectedSchemaId, setSelectedSchemaId] = useState('');
  const [savingSchema, setSavingSchema] = useState(false);
  const [linkingSchema, setLinkingSchema] = useState(false);
  const [useBuilder, setUseBuilder] = useState(false);
  const [builderFields, setBuilderFields] = useState<SchemaField[]>([]);

  const [gradings, setGradings] = useState<Grading[]>([]);
  const [publishingAll, setPublishingAll] = useState(false);
  const [loadingGradings, setLoadingGradings] = useState(false);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role!)) {
      loadData();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role!))) {
      setLoading(false);
    }
  }, [examId, user, authLoading]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const examData = await apiGet<Exam>(`/exams/${examId}/`);
      setExam(examData);

      const [classesData, subjectsData, keyData, samplesData, schemaData, allSchemasData] = await Promise.all([
        apiGet<Class[]>('/classes/').catch(() => []),
        apiGet<Subject[]>('/subjects/').catch(() => []),
        apiGet<{ id: string; questions: Question[]; sample_sheets: SampleSheet[] } | null>(`/exams/${examId}/answer-key/`).catch(() => null),
        apiGet<SampleSheet[]>(`/exams/${examId}/sample-sheets/`).catch(() => []),
        apiGet<ResultSchema | null>(`/exams/${examId}/result-schema/`).catch(() => null),
        apiGet<ResultSchema[]>('/exams/result-schemas/').catch(() => []),
      ]);

      setClasses(classesData);
      setSubjects(subjectsData);
      setAnswerKey(keyData);
      setSamples(samplesData);
      setResultSchema(schemaData);
      setAllSchemas(allSchemasData);
      if (keyData) setQuestions(keyData.questions);
      if (schemaData) {
        setSchemaName(schemaData.name);
        setSchemaDescription(schemaData.description || '');
        setSelectedSchemaId(schemaData.id);
        setBuilderFields(jsonSchemaToFields(schemaData.schema_definition));
        setUseBuilder(true);
      }

      try {
        const pending = await getSheetsForExam(examId, 'pending_mapping');
        setPendingSheetsCount(pending.length);
      } catch {
        setPendingSheetsCount(0);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load exam data');
    } finally {
      setLoading(false);
    }
  };

  const loadGradings = async () => {
    try {
      setLoadingGradings(true);
      const gradingsData = await apiGet<Grading[]>(`/exams/${examId}/gradings`);
      setGradings(gradingsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load gradings');
    } finally {
      setLoadingGradings(false);
    }
  };

  const handlePublishAll = async () => {
    if (!confirm('Publish all reviewed/overridden gradings for this exam? This will make results visible to students.')) return;
    try {
      setPublishingAll(true);
      const result = await publishAllGradings(examId);
      setSuccess(`Published ${result.published_count} grading(s)`);
      await loadGradings();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to publish all gradings');
    } finally {
      setPublishingAll(false);
    }
  };

  const handleSaveAnswerKey = async () => {
    try {
      await apiPost(`/exams/${examId}/answer-key/`, {
        exam_id: examId,
        questions,
        sample_sheets: samples,
        source: 'manual',
        source_file: null,
      });
      loadData();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save answer key');
    }
  };

  const handleAddQuestion = () => {
    setEditingQuestion(questions.length);
    setQuestionForm({
      q_no: `${questions.length + 1}`,
      question: null,
      expected_answer: null,
      marks: 0,
      keywords: [],
      marking_scheme: null,
    });
  };

  const handleSaveQuestion = () => {
    if (editingQuestion !== null && editingQuestion < questions.length) {
      const updated = [...questions];
      updated[editingQuestion] = questionForm;
      setQuestions(updated);
    } else {
      setQuestions([...questions, questionForm]);
    }
    setEditingQuestion(null);
  };

  const handleDeleteQuestion = (index: number) => {
    setQuestions(questions.filter((_, i) => i !== index));
  };

  const handleEditQuestion = (index: number) => {
    setEditingQuestion(index);
    setQuestionForm({ ...questions[index] });
  };

  const handleUploadSample = async (e: React.FormEvent) => {
    e.preventDefault();
    const fileInput = document.getElementById('sample-file') as HTMLInputElement;
    if (!fileInput.files || fileInput.files.length === 0) return;

    setUploadingSample(true);
    try {
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('label', sampleLabel);
      if (sampleNotes) formData.append('notes', sampleNotes);

      await uploadFile(`/exams/${examId}/sample-sheets/`, formData);
      setSampleLabel('');
      setSampleNotes('');
      fileInput.value = '';
      loadData();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload sample');
    } finally {
      setUploadingSample(false);
    }
  };

  const handleDeleteSample = async (index: number) => {
    if (!confirm('Delete this sample sheet?')) return;
    try {
      await apiDelete(`/exams/${examId}/sample-sheets/${index}/`);
      loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete sample');
    }
  };

  const handleSaveResultSchema = async () => {
    const finalSchemaName = schemaName.trim() || `${exam?.title || 'Exam'} Result Schema`;
    if (builderFields.length === 0) {
      setError('Add at least one field in the schema builder');
      return;
    }
    setSavingSchema(true);
    setError(null);
    setSuccess(null);
    try {
      const schemaDef = fieldsToJsonSchema(builderFields);
      if (selectedSchemaId && resultSchema) {
        await apiPatch(`/exams/result-schemas/${selectedSchemaId}/`, {
          name: finalSchemaName,
          description: schemaDescription || undefined,
          schema_definition: schemaDef,
        });
        setSuccess('Result schema updated successfully');
      } else {
        const newSchema = await apiPost<ResultSchema>(`/exams/${examId}/result-schema/`, {
          name: finalSchemaName,
          description: schemaDescription || undefined,
          schema_definition: schemaDef,
        });
        setSelectedSchemaId(newSchema.id);
        setSuccess('Result schema created and linked to exam successfully');
      }
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save schema');
    } finally {
      setSavingSchema(false);
    }
  };

  const handleLinkExistingSchema = async () => {
    if (!selectedSchemaId) return;
    setLinkingSchema(true);
    setError(null);
    setSuccess(null);
    try {
      await apiPatch(`/exams/${examId}/`, { result_schema_id: selectedSchemaId });
      setSuccess('Result schema linked to exam successfully');
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to link schema');
    } finally {
      setLinkingSchema(false);
    }
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user || !['admin', 'teacher'].includes(user.role!)) {
    return <div>Access denied</div>;
  }

  if (!exam) {
    return <div>Exam not found</div>;
  }

  const subject = subjects.find(s => s.id === exam.subject_id);
  const cls = classes.find(c => c.id === exam.class_id);

  const tabs: { key: Tab; label: string }[] = [
    { key: 'overview', label: 'Overview' },
    { key: 'question-paper', label: 'Question Paper' },
    { key: 'answer-key', label: 'Answer Key' },
    { key: 'samples', label: 'Sample Sheets' },
    { key: 'students', label: 'Enrolled Students' },
    { key: 'upload-sheets', label: pendingSheetsCount > 0 ? `Upload Sheets (${pendingSheetsCount})` : 'Upload Sheets' },
    { key: 'batches', label: 'Batches' },
    { key: 'results', label: 'Results' },
  ];


  return (
    <div>
      <div style={{ marginBottom: '2rem' }}>
        <Link href="/exams" className="btn btn-secondary" style={{ marginBottom: '1rem' }}>
          Back to Exams
        </Link>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h1 className="text-xl" style={{ marginBottom: '0.5rem', fontWeight: 700 }}>{exam.title}</h1>
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
              <span>{subject?.name || 'Unknown Subject'}</span>
              <span>&bull;</span>
              <span>{cls ? `${cls.name}${cls.section ? ` - ${cls.section}` : ''}` : 'Unknown Class'}</span>
              <span>&bull;</span>
              <span className="node node-teal">{cls?.session || 'N/A'}</span>
              <span>&bull;</span>
              <span>{exam.total_marks} marks</span>
              <span className={`node node-${exam.complexity_tier === 'simple' ? 'green' : exam.complexity_tier === 'complex' ? 'red' : 'blue'}`}>
                {exam.complexity_tier}
              </span>
              <span className={`node node-${exam.status === 'draft' ? 'yellow' : 'green'}`}>
                {exam.status}
              </span>
              {pendingSheetsCount > 0 && (
                <span className="node node-orange">
                  {pendingSheetsCount} pending mapping
                </span>
              )}
            </div>
          </div>
          {pendingSheetsCount > 0 && (
            <Link href={`/exams/${examId}/upload`} className="btn btn-primary">
              Start Mapping
            </Link>
          )}
        </div>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      {success && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--success-bg)', border: '1px solid var(--success)', borderRadius: 'var(--radius-md)', color: 'var(--success-text)', fontSize: '0.875rem' }}>
          {success}
          <button onClick={() => setSuccess(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem', overflowX: 'auto', flexWrap: 'nowrap' }}>
        {tabs.map(tab => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => setActiveTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div className="panel" style={{ padding: '1.5rem' }}>
          <h2 className="text-lg" style={{ fontWeight: 600, marginBottom: '1rem' }}>Exam Details</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div>
              <label className="form-label">Title</label>
              <div style={{ padding: '0.5rem 0' }}>{exam.title}</div>
            </div>
            <div>
              <label className="form-label">Subject</label>
              <div style={{ padding: '0.5rem 0' }}>{subject?.name || '-'}</div>
            </div>
            <div>
              <label className="form-label">Class</label>
              <div style={{ padding: '0.5rem 0' }}>{cls ? `${cls.name}${cls.section ? ` - ${cls.section}` : ''}` : '-'}</div>
            </div>
            <div>
              <label className="form-label">Session</label>
              <div style={{ padding: '0.5rem 0' }}>
                {cls?.session ? (
                  <span className="node node-teal">{cls.session}</span>
                ) : '-'}
              </div>
            </div>
            <div>
              <label className="form-label">Total Marks</label>
              <div style={{ padding: '0.5rem 0' }}>{exam.total_marks}</div>
            </div>
            <div>
              <label className="form-label">Complexity Tier</label>
              <div style={{ padding: '0.5rem 0' }}>
                <span className={`node node-${exam.complexity_tier === 'simple' ? 'green' : exam.complexity_tier === 'complex' ? 'red' : 'blue'}`}>
                  {exam.complexity_tier}
                </span>
              </div>
            </div>
            <div>
              <label className="form-label">Scheduled On</label>
              <div style={{ padding: '0.5rem 0' }}>{exam.scheduled_on || '-'}</div>
            </div>
            <div>
              <label className="form-label">Grading Rubric</label>
              <div style={{ padding: '0.5rem 0' }}>
                <span className={`node node-${exam.grading_rubric === 'strict' ? 'red' : exam.grading_rubric === 'lenient' ? 'green' : 'blue'}`}>
                  {exam.grading_rubric}
                </span>
              </div>
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">Rubric Notes</label>
              <div style={{ padding: '0.5rem 0', color: 'var(--text-secondary)' }}>{exam.rubric_notes || '-'}</div>
            </div>
            <div>
              <label className="form-label">Answer Key</label>
              <div style={{ padding: '0.5rem 0' }}>
                {exam.answer_key_id ? (
                  <span className="node node-green">Attached</span>
                ) : (
                  <span style={{ color: 'var(--text-secondary)' }}>Not set</span>
                )}
              </div>
            </div>
            <div>
              <label className="form-label">Result Schema</label>
              <div style={{ padding: '0.5rem 0' }}>
                {resultSchema ? (
                  <span className="node node-purple">{resultSchema.name}</span>
                ) : (
                  <span style={{ color: 'var(--text-secondary)' }}>Not set</span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <div style={{ display: activeTab === 'question-paper' ? 'block' : 'none' }}>
        <QuestionPaperTab examId={examId} totalMarks={exam.total_marks} />
      </div>


      {activeTab === 'answer-key' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 className="text-md" style={{ fontWeight: 600 }}>Answer Key Questions</h2>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn btn-primary" onClick={handleAddQuestion}>
                Add Question
              </button>
              <button className="btn btn-primary" onClick={handleSaveAnswerKey} disabled={questions.length === 0}>
                Save Answer Key
              </button>
            </div>
          </div>

          <div className="panel" style={{ padding: '1rem' }}>
            {questions.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>No questions defined. Click "Add Question" to start.</p>
            ) : (
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Q No</th>
                      <th>Marks</th>
                      <th>Question</th>
                      <th>Expected Answer</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {questions.map((q, i) => (
                      <tr key={i}>
                        <td>
                          <span className="node node-blue">{q.q_no}</span>
                        </td>
                        <td>{q.marks}</td>
                        <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {q.question || '-'}
                        </td>
                        <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {q.expected_answer || '-'}
                        </td>
                        <td style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-secondary" onClick={() => handleEditQuestion(i)}>
                            Edit
                          </button>
                          <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDeleteQuestion(i)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {editingQuestion !== null && (
            <div className="modal-overlay" onClick={() => setEditingQuestion(null)}>
              <div className="modal-content" style={{ maxWidth: '600px' }} onClick={(e) => e.stopPropagation()}>
                <h2>{editingQuestion < questions.length ? 'Edit' : 'Add'} Question</h2>
                <div className="form-group">
                  <label className="form-label">Question Number</label>
                  <input type="text" className="form-input" value={questionForm.q_no} onChange={(e) => setQuestionForm({ ...questionForm, q_no: e.target.value })} required />
                </div>
                <div className="form-group">
                  <label className="form-label">Marks</label>
                  <input type="number" className="form-input" value={questionForm.marks} onChange={(e) => setQuestionForm({ ...questionForm, marks: parseInt(e.target.value) || 0 })} required min={0} />
                </div>
                <div className="form-group">
                  <label className="form-label">Question Text (optional)</label>
                  <textarea className="form-input" value={questionForm.question || ''} onChange={(e) => setQuestionForm({ ...questionForm, question: e.target.value || null })} rows={2} />
                </div>
                <div className="form-group">
                  <label className="form-label">Expected Answer (optional)</label>
                  <textarea className="form-input" value={questionForm.expected_answer || ''} onChange={(e) => setQuestionForm({ ...questionForm, expected_answer: e.target.value || null })} rows={3} />
                </div>
                <div className="form-group">
                  <label className="form-label">Marking Scheme (optional)</label>
                  <textarea className="form-input" value={questionForm.marking_scheme || ''} onChange={(e) => setQuestionForm({ ...questionForm, marking_scheme: e.target.value || null })} rows={2} />
                </div>
                <div className="form-group">
                  <label className="form-label">Keywords (comma-separated)</label>
                  <input type="text" className="form-input" value={questionForm.keywords.join(', ')} onChange={(e) => setQuestionForm({ ...questionForm, keywords: e.target.value.split(',').map(k => k.trim()).filter(Boolean) })} />
                </div>
                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'flex-end' }}>
                  <button className="btn btn-secondary" onClick={() => setEditingQuestion(null)}>Cancel</button>
                  <button className="btn btn-primary" onClick={handleSaveQuestion}>Save</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'samples' && (
        <div>
          <h2 className="text-lg" style={{ fontWeight: 600, marginBottom: '1rem' }}>Sample Answer Sheets</h2>

          <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
            <form onSubmit={handleUploadSample}>
              <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                <div>
                  <label className="form-label">File</label>
                  <input type="file" id="sample-file" className="form-input" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt" required />
                </div>
                <div>
                  <label className="form-label">Label</label>
                  <input type="text" className="form-input" value={sampleLabel} onChange={(e) => setSampleLabel(e.target.value)} placeholder="e.g., Full marks example" required />
                </div>
                <div>
                  <label className="form-label">Notes (optional)</label>
                  <input type="text" className="form-input" value={sampleNotes} onChange={(e) => setSampleNotes(e.target.value)} placeholder="Guidance for AI..." />
                </div>
                <button className="btn btn-primary" type="submit" disabled={uploadingSample}>
                  {uploadingSample ? 'Uploading...' : 'Upload Sample'}
                </button>
              </div>
            </form>
          </div>

          <div className="panel" style={{ padding: '1rem' }}>
            {samples.length === 0 ? (
              <p style={{ color: 'var(--text-secondary)', textAlign: 'center' }}>No sample sheets uploaded.</p>
            ) : (
              <div className="table-container">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Label</th>
                      <th>Type</th>
                      <th>Notes</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {samples.map((s, i) => (
                      <tr key={i}>
                        <td>
                          <span className="node node-teal">{s.label}</span>
                        </td>
                        <td>
                          <span className="node node-purple">{s.kind.toUpperCase()}</span>
                        </td>
                        <td style={{ color: 'var(--text-secondary)' }}>{s.notes || '-'}</td>
                        <td>
                          <button className="btn" style={{ color: 'var(--error)' }} onClick={() => handleDeleteSample(i)}>
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'students' && (
        <StudentsTab examId={examId} />
      )}

      {activeTab === 'result-schema' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 className="text-md" style={{ fontWeight: 600 }}>Result Schema</h2>
            <Link href="/result-schemas" className="btn btn-secondary">
              Manage Schemas
            </Link>
          </div>

          <div className="panel" style={{ padding: '1rem', marginBottom: '1.5rem' }}>
            <h3 className="text-sm" style={{ fontWeight: 600, marginBottom: '0.75rem' }}>Link Existing Schema</h3>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end' }}>
              <div style={{ flex: 1 }}>
                <label className="form-label">Select Schema</label>
                <select className="form-input" value={selectedSchemaId} onChange={(e) => setSelectedSchemaId(e.target.value)}>
                  <option value="">None</option>
                  {allSchemas.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <button className="btn btn-primary" onClick={handleLinkExistingSchema} disabled={!selectedSchemaId || linkingSchema}>
                {linkingSchema ? 'Linking...' : 'Link to Exam'}
              </button>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <span style={{ color: 'var(--text-muted)' }}>or</span>
            <button className="btn btn-secondary" onClick={() => setUseBuilder(!useBuilder)}>
              {useBuilder ? 'Hide' : 'Use'} Schema Builder
            </button>
          </div>

          {useBuilder && (
            <div className="panel" style={{ padding: '1rem' }}>
              <h3 className="text-sm" style={{ fontWeight: 600, marginBottom: '0.75rem' }}>
                {resultSchema ? 'Edit Current Schema' : 'Create New Schema'}
              </h3>
              <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <label className="form-label">Schema Name</label>
                  <input type="text" className="form-input" value={schemaName} onChange={(e) => setSchemaName(e.target.value)} placeholder="e.g., Standard Written Paper" />
                </div>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <label className="form-label">Description (optional)</label>
                  <input type="text" className="form-input" value={schemaDescription} onChange={(e) => setSchemaDescription(e.target.value)} placeholder="Brief description..." />
                </div>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <SchemaBuilder initialFields={builderFields} onChange={setBuilderFields} />
              </div>

              <button className="btn btn-primary" onClick={handleSaveResultSchema} disabled={savingSchema || builderFields.length === 0}>
                {savingSchema ? 'Saving...' : resultSchema ? 'Update & Link Schema' : 'Create & Link Schema'}
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'upload-sheets' && (
        <div>
          {pendingSheetsCount > 0 && (
            <div className="panel" style={{ padding: '1.5rem', marginBottom: '1.5rem', border: '2px solid var(--accent-primary)' }}>
              <div style={{ textAlign: 'center' }}>
                <h2 className="text-lg" style={{ marginBottom: '0.5rem', fontWeight: 600 }}>Sheets Ready for Mapping</h2>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  You have <strong style={{ color: 'var(--accent-primary)' }}>{pendingSheetsCount} answer sheet(s)</strong> waiting to be mapped to students.
                </p>
                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
                  <Link href={`/exams/${examId}/upload`} className="btn btn-primary" style={{ fontSize: '1.05rem', padding: '0.75rem 2rem' }}>
                    Start One-by-One Mapping
                  </Link>
                  <button className="btn btn-secondary" style={{ color: 'var(--error)', border: '1px solid var(--error)' }} onClick={() => {
                    if (confirm(`Remove all ${pendingSheetsCount} unmapped sheets? This will delete the PDFs and page images permanently.`)) {
                      deleteAllPendingSheets(examId)
                        .then(() => loadData())
                        .catch((err: Error) => setError(err.message));
                    }
                  }}>
                    Remove All Pending ({pendingSheetsCount})
                  </button>
                </div>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.75rem' }}>
                  Review each PDF, edit student details, delete wrong pages, then Save & Next
                </p>
              </div>
            </div>
          )}

          <div className="panel" style={{ padding: '1.5rem' }}>
            <ZipUpload examId={examId} onUploadComplete={loadData} />
          </div>
        </div>
      )}

      {activeTab === 'batches' && (
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1rem' }}>
            Batch management has been moved to a dedicated page.
          </p>
          <Link href={`/exams/${examId}/batches`} className="btn btn-primary" style={{ padding: '0.75rem 2rem' }}>
            Go to Batches
          </Link>
        </div>
      )}

      {activeTab === 'results' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <h2 className="text-md" style={{ fontWeight: 600 }}>Grading Results</h2>
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <button className="btn btn-secondary" onClick={loadGradings} disabled={loadingGradings}>
                {loadingGradings ? 'Loading...' : 'Refresh'}
              </button>
              <button className="btn btn-primary" onClick={handlePublishAll} disabled={publishingAll} style={{ color: 'var(--success)', border: '1px solid var(--success)' }}>
                {publishingAll ? 'Publishing...' : 'Publish All'}
              </button>
            </div>
          </div>

          {loadingGradings ? (
            <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
              <p style={{ color: 'var(--text-muted)' }}>Loading gradings...</p>
            </div>
          ) : gradings.length === 0 ? (
            <div className="panel" style={{ padding: '2rem', textAlign: 'center' }}>
              <p style={{ color: 'var(--text-muted)' }}>No gradings yet. Submit a batch to start AI grading.</p>
            </div>
          ) : (
            <div className="table-container">
              <table className="table">
                <thead>
                  <tr>
                    <th>Student</th>
                    <th>Roll No</th>
                    <th style={{ textAlign: 'center' }}>Score</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {gradings.map((g) => {
                    const pct = g.total_max > 0 ? Math.round((g.total_awarded / g.total_max) * 100) : 0;
                    const scoreColor = pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)';
                    return (
                      <tr key={g.id}>
                        <td style={{ fontWeight: 500 }}>{(g.result as any)?.student?.name || 'Unknown'}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{(g.result as any)?.student?.roll_no || '-'}</td>
                        <td style={{ textAlign: 'center' }}>
                          <span style={{ fontWeight: 700, color: scoreColor }}>{g.total_awarded}/{g.total_max}</span>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '0.5rem' }}>({pct}%)</span>
                        </td>
                        <td>
                          <span className={`node node-${g.status === 'published' ? 'green' : g.status === 'auto' ? 'blue' : 'yellow'}`}>
                            {g.status}
                          </span>
                        </td>
                        <td>
                          <Link href={`/sheets/${g.sheet_id}`} className="btn btn-secondary">
                            Review
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
