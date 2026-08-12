const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

async function getToken() {
  return localStorage.getItem('auth_token');
}

export async function apiFetch(
  endpoint: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = await getToken();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
  } catch (err) {
    throw new Error('Network error - is the backend running?');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
  return res;
}

function normalizeEndpoint(endpoint: string): string {
  const qIndex = endpoint.indexOf('?');
  if (qIndex !== -1) {
    const path = endpoint.substring(0, qIndex);
    const query = endpoint.substring(qIndex);
    const normalizedPath = path.endsWith('/') ? path : `${path}/`;
    return normalizedPath + query;
  }
  return endpoint.endsWith('/') ? endpoint : `${endpoint}/`;
}

export async function apiGet<T>(endpoint: string): Promise<T> {
  const res = await apiFetch(normalizeEndpoint(endpoint));
  return res.json();
}

export async function apiPost<T>(endpoint: string, body: unknown): Promise<T> {
  const res = await apiFetch(normalizeEndpoint(endpoint), {
    method: 'POST',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function apiPatch<T>(endpoint: string, body: unknown): Promise<T> {
  const res = await apiFetch(normalizeEndpoint(endpoint), {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function apiDelete<T>(endpoint: string): Promise<T> {
  const res = await apiFetch(normalizeEndpoint(endpoint), { method: 'DELETE' });
  return res.json();
}

export async function uploadFile(
  endpoint: string,
  formData: FormData
): Promise<Record<string, unknown>> {
  const token = await getToken();
  const res = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface SheetPage {
  id: string;
  sheet_id: string;
  page_no: number;
  image_path: string;
  width: number;
  height: number;
  is_deleted: boolean;
  created_at: string;
}

export interface AnswerSheet {
  id: string;
  exam_id: string;
  subject_id: string | null;
  student_name: string | null;
  roll_no: string | null;
  class_label: string | null;
  original_filename: string;
  student_id: string | null;
  original_pdf_path: string | null;
  page_count: number;
  status: string;
  current_batch_id: string | null;
  uploaded_by: string | null;
  batch_upload_id: string | null;
  created_at: string;
  updated_at: string | null;
}

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('auth_token');
}

function withToken(url: string): string {
  const token = getAuthToken();
  return token ? `${url}${url.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}` : url;
}

export function getPageImageUrl(sheetId: string, pageNo: number): string {
  return withToken(`/api/files/sheets/${sheetId}/pages/${pageNo}`);
}

export async function getSheetsForExam(examId: string, statusFilter?: string): Promise<AnswerSheet[]> {
  const query = statusFilter ? `?status_filter=${statusFilter}` : '';
  return apiGet<AnswerSheet[]>(`/exams/${examId}/sheets${query}`);
}

export async function getSheet(sheetId: string): Promise<AnswerSheet> {
  return apiGet<AnswerSheet>(`/exams/sheets/${sheetId}`);
}

export async function getSheetPages(sheetId: string): Promise<SheetPage[]> {
  return apiGet<SheetPage[]>(`/exams/sheets/${sheetId}/pages`);
}

export async function updateSheetMapping(
  sheetId: string,
  mapping: {
    student_name?: string;
    roll_no?: string;
    class_label?: string;
    student_id?: string;
  }
): Promise<AnswerSheet> {
  return apiPatch<AnswerSheet>(`/exams/sheets/${sheetId}`, mapping);
}

export async function deleteSheetPage(sheetId: string, pageNo: number): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = { 'Content-Type': 'application/json' };
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/sheets/${sheetId}/pages/${pageNo}/`, {
    method: 'PATCH',
    headers,
    body: '{}',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
}

export async function skipSheet(sheetId: string): Promise<AnswerSheet> {
  return apiPost<AnswerSheet>(`/exams/sheets/${sheetId}/skip`, {});
}

export async function deleteSheet(sheetId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/sheets/${sheetId}/`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
}

export async function deleteAllPendingSheets(examId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/${examId}/sheets/pending/`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
}

export async function deleteUploadBatch(examId: string, batchId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/${examId}/sheets/upload-batches/${batchId}/`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
}

export interface BatchItem {
  id: string;
  batch_id: string;
  sheet_id: string;
  custom_id: string;
  prompt_preview: string | null;
  status: string;
  error: string | null;
  raw_response: Record<string, unknown> | null;
  created_at: string;
}

export interface BatchJob {
  id: string;
  exam_id: string;
  provider: string;
  model: string;
  provider_batch_id: string | null;
  input_file_path: string | null;
  output_file_path: string | null;
  item_count: number;
  completed_count: number;
  failed_count: number;
  status: string;
  submitted_at: string | null;
  completed_at: string | null;
  last_polled_at: string | null;
  poll_error: string | null;
  created_by: string | null;
  created_at: string;
}

export interface BatchDetail extends BatchJob {
  items: BatchItem[];
}

export async function createBatch(
  examId: string,
  data?: { provider?: string; model?: string }
): Promise<BatchJob> {
  const params = new URLSearchParams();
  if (data) {
    if (data.provider) params.append('provider', data.provider);
    if (data.model) params.append('model', data.model);
  }
  const query = params.toString();
  // Send empty body with query params
  return apiPost<BatchJob>(`/exams/${examId}/batches${query ? '?' + query : ''}`, {});
}

export async function getBatchesForExam(examId: string): Promise<BatchJob[]> {
  return apiGet<BatchJob[]>(`/exams/${examId}/batches`);
}

export async function getBatch(batchId: string): Promise<BatchDetail> {
  return apiGet<BatchDetail>(`/exams/batches/${batchId}`);
}

export async function downloadBatchJsonl(batchId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/batches/${batchId}/jsonl/`, {
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `batch_${batchId}_input.jsonl`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function deleteBatchItem(batchId: string, itemId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/batches/${batchId}/items/${itemId}/`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
}

export async function updateBatch(
  batchId: string,
  data: {
    provider?: string;
    model?: string;
    status?: string;
  }
): Promise<BatchJob> {
  return apiPatch<BatchJob>(`/exams/batches/${batchId}`, data);
}

export async function uploadFilesForBatch(batchId: string): Promise<BatchJob> {
  return apiPost<BatchJob>(`/exams/batches/${batchId}/submit`, {});
}

export async function submitToGemini(batchId: string): Promise<BatchJob> {
  return apiPost<BatchJob>(`/exams/batches/${batchId}/submit-to-gemini`, {});
}

export async function downloadFinalJsonl(batchId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/batches/${batchId}/jsonl-final/`, {
    headers,
  });
  if (!res.ok) throw new Error('Failed to download JSONL');
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `batch_${batchId}_final.jsonl`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export interface UploadStatus {
  batch_id: string;
  status: string;
  upload_progress: {
    phase: string;
    current: number;
    total: number;
    message: string;
  } | null;
}

export async function getBatchUploadStatus(batchId: string): Promise<UploadStatus> {
  return apiGet<UploadStatus>(`/exams/batches/${batchId}/upload-status`);
}

export async function cancelBatch(batchId: string): Promise<BatchJob> {
  return apiPost<BatchJob>(`/exams/batches/${batchId}/cancel`, {});
}

export async function refreshBatch(batchId: string): Promise<BatchDetail> {
  return apiPost<BatchDetail>(`/exams/batches/${batchId}/refresh`, {});
}

export async function deleteBatch(batchId: string): Promise<void> {
  const token = await getToken();
  const headers: HeadersInit = {};
  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/exams/batches/${batchId}/`, {
    method: 'DELETE',
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
}

export interface Grading {
  id: string;
  sheet_id: string;
  exam_id: string;
  batch_id: string;
  student_id: string | null;
  result_schema_id: string | null;
  result: Record<string, unknown>;
  total_awarded: number;
  total_max: number;
  status: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  published_at: string | null;
  override_log: Array<Record<string, unknown>>;
  created_at: string;
}

export async function getBatchGradings(batchId: string): Promise<Grading[]> {
  return apiGet<Grading[]>(`/exams/batches/${batchId}/gradings`);
}

export async function getGrading(gradingId: string): Promise<Grading> {
  return apiGet<Grading>(`/exams/gradings/${gradingId}`);
}

export async function updateGrading(
  gradingId: string,
  data: Record<string, unknown>
): Promise<Grading> {
  return apiPatch<Grading>(`/exams/gradings/${gradingId}`, data);
}

export async function publishGrading(gradingId: string): Promise<Grading> {
  return apiPost<Grading>(`/exams/gradings/${gradingId}/publish`, {});
}

export async function publishAllGradings(examId: string): Promise<{ published_count: number }> {
  return apiPost<{ published_count: number }>(`/exams/${examId}/publish-all`, {});
}

// ============================================================
// Question Paper APIs (Phase 4)
// ============================================================

export interface QPPage {
  page_no: number;
  image_path: string;
  is_instruction_page: boolean;
  has_questions: boolean;
  has_diagrams: boolean;
  has_graphs: boolean;
  is_needed_for_grading: boolean;
  reason: string;
}

export interface QPExtractedQuestion {
  q_no: string;
  question: string | null;
  question_page_refs: number[];
  expected_answer: string | null;
  marks: number;
  keywords: string[];
  marking_scheme: string | null;
  marking_scheme_page_ref: number | null;
  has_diagram: boolean;
  diagram_page_refs: number[];
  attached_images?: QuestionPaperCrop[];
}

export interface QuestionPaper {
  id: string;
  exam_id: string;
  source_file: string;
  total_pages: number;
  pages: QPPage[];
  extracted_questions: QPExtractedQuestion[];
  status: string;
  extraction_model: string | null;
  warnings: string[];
  created_at: number;
  updated_at: number | null;
}

export interface ExtractionTask {
  id: string;
  exam_id: string;
  status: string;
  total_pages: number;
  processed_pages: number;
  current_page: number;
  current_step: string;
  questions_found_so_far: number;
  error: string | null;
  started_at: number | null;
  completed_at: number | null;
}

export async function uploadQuestionPaper(examId: string, file: File): Promise<{ message: string; task_id: string; file_path: string }> {
  const token = await getToken();
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/exams/${examId}/question-paper/upload/`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getQuestionPaper(examId: string): Promise<QuestionPaper | null> {
  return apiGet<QuestionPaper | null>(`/exams/${examId}/question-paper`);
}

export async function getExtractionStatus(examId: string): Promise<ExtractionTask> {
  return apiGet<ExtractionTask>(`/exams/${examId}/question-paper/extraction-status`);
}

export async function reviewQuestionPaper(
  examId: string,
  included_page_refs: number[],
  excluded_page_refs: number[],
  questions?: QPExtractedQuestion[],
): Promise<{ message: string }> {
  return apiPost<{ message: string }>(`/exams/${examId}/question-paper/review`, {
    included_page_refs,
    excluded_page_refs,
    questions: questions || undefined,
  });
}

export function getQuestionPaperPageUrl(examId: string, pageNo: number): string {
  return withToken(`${API_BASE}/files/question-papers/${examId}/pages/${pageNo}`);
}

export function getCropImageUrl(examId: string, cropId: string): string {
  return withToken(`${API_BASE}/files/question-papers/${examId}/crops/${cropId}`);
}

export function getAdditionalPdfPageUrl(examId: string, pdfId: string, pageNo: number): string {
  return withToken(`${API_BASE}/files/question-papers/${examId}/additional/${pdfId}/pages/${pageNo}`);
}

export function getAdditionalPdfOriginalUrl(examId: string, pdfId: string): string {
  return withToken(`${API_BASE}/files/question-papers/${examId}/additional/${pdfId}/original`);
}

export function getSheetPageUrl(sheetId: string, pageNo: number): string {
  return `${API_BASE}/api/files/sheets/${sheetId}/pages/${pageNo}`;
}

// ============================================================
// Crop Models (Phase 4 — Split-Screen Review)
// ============================================================

export interface CropBBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface QuestionPaperCrop {
  id: string;
  exam_id: string;
  question_paper_id: string;
  question_index: number;
  q_no: string;
  image_path: string;
  source_pdf: string;
  page_no: number;
  bbox: CropBBox;
  created_at: number;
}

export interface AdditionalPdf {
  id: string;
  exam_id: string;
  source_file: string;
  label: string;
  type: string;
  total_pages: number;
  filename: string;
  created_at: number;
}

export async function createCrop(
  examId: string,
  data: {
    question_index: number;
    q_no: string;
    page_no: number;
    source_pdf: string;
    bbox: CropBBox;
    image_data_base64: string;
  }
): Promise<{ message: string; crop_id: string; crop: QuestionPaperCrop }> {
  return apiPost<{ message: string; crop_id: string; crop: QuestionPaperCrop }>(
    `/exams/${examId}/question-paper/crop`,
    data,
  );
}

export async function deleteCrop(examId: string, cropId: string): Promise<{ message: string }> {
  return apiDelete<{ message: string }>(`/exams/${examId}/question-paper/crop/${cropId}`);
}

export async function getCrops(
  examId: string,
  questionIndex?: number,
): Promise<{ crops: QuestionPaperCrop[] }> {
  const query = questionIndex !== undefined ? `?question_index=${questionIndex}` : '';
  return apiGet<{ crops: QuestionPaperCrop[] }>(
    `/exams/${examId}/question-paper/crops${query}`,
  );
}

export async function uploadAdditionalPdf(
  examId: string,
  file: File,
  label: string,
  pdfType: string = 'reference',
): Promise<AdditionalPdf> {
  const token = await getToken();
  const formData = new FormData();
  formData.append('file', file);
  formData.append('label', label);
  formData.append('pdf_type', pdfType);
  const res = await fetch(`${API_BASE}/exams/${examId}/question-paper/additional-pdf/`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getAdditionalPdfs(examId: string): Promise<{ pdfs: AdditionalPdf[] }> {
  return apiGet<{ pdfs: AdditionalPdf[] }>(`/exams/${examId}/question-paper/additional-pdfs`);
}

export async function deleteAdditionalPdf(
  examId: string,
  pdfId: string,
): Promise<{ message: string }> {
  return apiDelete<{ message: string }>(`/exams/${examId}/question-paper/additional-pdf/${pdfId}`);
}

// ============================================================
// Exam-Student Enrollment APIs (Phase 12)
// ============================================================

export interface ExamStudentsSummary {
  active_students: number;
  removed_students: number;
  mapped_sheets: number;
  unmapped_sheets: number;
}

export interface StudentDropdownItem {
  id: string;
  full_name: string;
  roll_no: string | null;
  email: string;
}

export async function syncExamStudents(examId: string): Promise<{ message: string; added_count: number; removed_count: number; total_active: number }> {
  return apiPost<{ message: string; added_count: number; removed_count: number; total_active: number }>(
    `/exams/${examId}/sync-students`,
    {},
  );
}

export async function getExamStudents(examId: string): Promise<any[]> {
  return apiGet<any[]>(`/exams/${examId}/students`);
}

export async function getExamStudentsSummary(examId: string): Promise<ExamStudentsSummary> {
  return apiGet<ExamStudentsSummary>(`/exams/${examId}/students/summary`);
}

export async function getExamStudentsDropdown(examId: string): Promise<StudentDropdownItem[]> {
  return apiGet<StudentDropdownItem[]>(`/exams/${examId}/students/dropdown`);
}

// ============================================================
// Auto-Match APIs (Phase 12)
// ============================================================

export interface AutoMatchSuggestion {
  sheet_id: string;
  original_filename: string;
  parsed_name: string | null;
  parsed_roll: string | null;
  matched_student: {
    student_id: string;
    full_name: string;
    roll_no: string | null;
    email: string;
  };
  confidence: number;
}

export interface AutoMatchRequest {
  matches: {
    sheet_id: string;
    student_id: string;
    keep_parsed_name: boolean;
  }[];
}

export async function getAutoMatchSuggestions(examId: string): Promise<{ suggestions: AutoMatchSuggestion[]; total_pending: number }> {
  return apiGet<{ suggestions: AutoMatchSuggestion[]; total_pending: number }>(
    `/exams/${examId}/sheets/auto-match/suggestions`,
  );
}

export async function applyAutoMatch(examId: string, request: AutoMatchRequest): Promise<{ matched_count: number; failed_count: number }> {
  return apiPost<{ matched_count: number; failed_count: number }>(
    `/exams/${examId}/sheets/auto-match`,
    request,
  );
}
