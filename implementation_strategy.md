# Answer Sheet Management System - Implementation Strategy

## Why Multiple Tasks (Not One Large Task)?
The project is too complex for a single task due to:
- **Dependencies**: Each phase blocks the next (Auth must exist before Users; Users before Exams, etc.)
- **Different skill domains**: Auth, CRUD APIs, UI components, AI integration, background workers
- **Testing checkpoints**: Each phase should be testable independently

---

## Detailed Phase-by-Phase Implementation Plan

### **Phase 1: Auth Core + Password Reset**
**Complexity: ★★★☆☆ | Estimated: 3-4 days**

**Backend Tasks:**
1. Create `backend/core/config.py` - environment variables (JWT_SECRET, etc.)
2. Create `backend/core/security.py` - password hashing (passlib), JWT creation/verification
3. Create `backend/models/auth.py` - User, PasswordReset models with Pydantic
4. Create `backend/routers/auth.py`:
   - `POST /auth/login` → JWT token
   - `GET /auth/me` → current user
   - `POST /auth/forgot-password` → generate reset token
   - `POST /auth/reset-password` → reset with token
   - `POST /auth/change-password` → authenticated reset
5. Create `backend/core/deps.py` - `get_current_user`, `require_roles()` dependencies
6. Update `backend/main.py` - mount auth router, add CORS with env config
7. Create bootstrap script for initial admin from `BOOTSTRAP_ADMIN_EMAIL/PASSWORD`

**Frontend Tasks:**
1. Create `frontend/src/lib/auth.tsx` - AuthContext (JWT in localStorage)
2. Create `frontend/src/lib/api.ts` - fetch wrapper that injects `Authorization: Bearer` header
3. Create `frontend/src/middleware.ts` - role guard middleware
4. Create pages: `/login`, `/forgot-password`, `/reset-password?token=...`, `/change-password`
5. Update `layout.tsx` - role-aware header with user info

**Deliverable:** Working login/logout flow with JWT, role-based access ready

---

### **Phase 2: Users / Classes / Subjects / Students**
**Complexity: ★★☆☆☆ | Estimated: 3-4 days**

**Backend Tasks:**
1. Create `backend/models/school.py` - User (extended), Class, Subject, Enrollment models
2. Create `backend/routers/users.py`:
   - `GET/POST /users` - list/create (admin/teacher only)
   - `PATCH/DELETE /users/{id}`
   - `POST /users/import` - CSV bulk import for students
3. Create `backend/routers/classes.py` - CRUD with teacher_ids array
4. Create `backend/routers/subjects.py` - CRUD linked to classes
5. Update `backend/db/database.py` - add new collections
6. Create indexes: unique email, sparse (class_id, roll_no)

**Frontend Tasks:**
1. Create `/users` page - list with role filter, create modal
2. Create CSV import component (drag-drop, preview, confirm)
3. Create `/classes` page - list, create/edit, assign teachers
4. Create `/subjects` page - list by class, create/edit
5. Add RBAC checks: Teachers can only manage their own classes

**Deliverable:** Can create classes, subjects, students (manually or CSV), assign teachers

---

### **Phase 3: Exams + Complexity Tier + Answer Keys + Result Schemas**
**Complexity: ★★★☆☆ | Estimated: 4-5 days**

**Backend Tasks:**
1. Create `backend/models/sheets.py` - Exam (with `complexity_tier`), AnswerKey, ResultSchema models
2. Create `backend/routers/exams.py`:
   - `POST /exams` - create exam with subject/class/complexity_tier
   - `PATCH /exams/{id}` - update status
   - `GET /exams?class_id=...`
3. Create `backend/routers/answer_keys.py`:
   - `POST /exams/{id}/answer-key` - JSON body (manual or hybrid mode)
   - `POST /exams/{id}/sample-sheets` - upload PDF/image/text
4. Add `COMPLEXITY_MODEL_MAP` to `backend/core/config.py`:
   ```python
   COMPLEXITY_MODEL_MAP = {
       "simple": "gemini-2.0-flash",
       "standard": "gemini-2.5-flash",
       "complex": "gemini-2.5-pro",
   }
   ```
5. Extend `backend/models/schemas.py` - add "result_schema" kind
6. Create result schema editor endpoint (reuse schemas collection)

**Frontend Tasks:**
1. Create `/exams` page - list, create modal with class/subject dropdowns + **complexity tier selector**
2. Create `/exams/[id]` page with tabs:
   - **Answer Key** tab: manual JSON editor OR QP upload with AI extraction
   - **Samples** tab: upload PDFs/images with labels
   - **Result Schema** tab: JSON-Schema editor (reuse existing patterns)
3. Complexity tier UI: dropdown on exam create/edit (Simple / Standard / Complex)
4. Display selected model based on complexity tier in exam detail view

**Deliverable:** Can create exams with complexity tier, upload answer keys (manual or PDF), attach sample sheets and result schemas

---

### **Phase 4: Question Paper Upload + AI Extraction + Split-Screen Review with Crop-to-Attach**
**Complexity: ★★★★★ | Estimated: 7-8 days**

**Backend Tasks:**
1. Create `backend/models/sheets.py` extensions:
   - `QuestionPaper`, `QuestionPaperPage` models
   - `ExtractionTask`, `ExtractionProgress` models
   - `QuestionPaperCrop` model (stores crop bbox, image path, question reference)
   - `AdditionalPdf` model (supplementary PDFs per exam)
2. Create `backend/services/question_extraction_service.py`:
   - `extract_question_paper(exam_id, pdf_path)` → extraction_task_id
   - Two-pass extraction: rasterize → per-page AI analysis → consolidation
   - Uses `gemini-2.0-flash` for extraction (cheap, fast, OCR+layout capable)
3. Create `backend/services/crop_service.py` (NEW):
   - `save_crop(exam_id, question_index, image_data, bbox, page_no, source_pdf)` → crop_id
   - Extracts region from PDF page using bbox, saves as PNG
   - `delete_crop(crop_id)` → removes image file and DB record
   - `get_crops_for_question(exam_id, question_index)` → list of crops
4. Create `backend/services/additional_pdf_service.py` (NEW):
   - `upload_additional_pdf(exam_id, file, label, type)` → pdf_id
   - `list_additional_pdfs(exam_id)` → list of PDFs
   - `delete_additional_pdf(pdf_id)` → removes file and DB record
5. Create `backend/routers/question_papers.py`:
   - `POST /exams/{id}/question-paper/upload` - upload QP PDF, trigger extraction
   - `GET /exams/{id}/question-paper/` - get QP with extracted questions + attached crops
   - `GET /exams/{id}/question-paper/extraction-status` - poll extraction progress
   - `POST /exams/{id}/question-paper/review` - teacher confirms pages, saves edits, saves attached images
   - `POST /exams/{id}/question-paper/crop` - upload cropped image (multipart/base64), attach to question
   - `DELETE /exams/{id}/question-paper/crop/{crop_id}` - remove attached image from question
   - `POST /exams/{id}/question-paper/additional-pdf` - upload supplementary PDF
   - `GET /exams/{id}/question-paper/additional-pdfs` - list all additional PDFs
   - `DELETE /exams/{id}/question-paper/additional-pdf/{pdf_id}` - remove additional PDF
6. Create `backend/workers/extraction_worker.py`:
   - Asyncio task, listens for new extraction tasks
   - Runs: rasterize → analyze pages (parallel) → consolidate → save results
   - Updates `extraction_tasks` status in real-time
7. Update `backend/routers/files.py`:
   - `GET /files/question-papers/{exam_id}/pages/{n}` - serve QP page image
   - `GET /files/question-papers/{exam_id}/crops/{crop_id}` - serve cropped attachment image
   - `GET /files/question-papers/{exam_id}/additional/{pdf_id}/pages/{n}` - serve additional PDF page
8. Update `backend/db/database.py` - add `question_papers`, `extraction_tasks`, `question_paper_crops`, `additional_pdfs` collections
9. Update `backend/main.py` - start extraction worker on startup

**Frontend Tasks:**
1. Add **Tab 1: "Upload Question Paper"** to `/exams/[id]/answer-key`:
   - Drag-drop multi-page PDF upload
   - Real-time extraction progress display:
     - "Converting PDF to images (25 pages)"
     - "Analyzing pages with AI (18/25)" with progress bar
     - "Consolidating results"
   - Polls extraction status every 2 seconds
   - Auto-redirects to review tab on completion
   - Error state with retry option

2. Add **Tab 2: "Review Questions" — Split-Screen with Crop-to-Attach**:
   - **Split-screen layout** (CSS grid, 60/40 split):
     - **Left panel (60%)**: Full PDF viewer
       - Renders pages via pdf.js on a canvas
       - Supports pan, zoom, and region selection (click-drag crop)
       - Tab bar at top: "Question Paper (original.pdf)" + additional PDFs
       - [+ Add PDF] button to upload supplementary PDFs
       - When region is cropped, floating popup shows cropped thumbnail with:
         - "Attach to Q{q_no}" button (targets active question)
         - "Dismiss" button
       - If no question is active, popup shows "Select a question first"
     - **Right panel (40%)**: Scrollable list of extracted questions
       - Each question is a collapsible card: Q.No, text, marks, has_diagram indicator
       - Click question → becomes "active" (highlighted border), expands to show edit form:
         - Editable fields: question text, marks, keywords, expected answer, marking scheme
         - **Attached images section**: thumbnails of crops with [Remove] button
         - [Save] button per question
       - Only one question active at a time
   - **Multi-PDF workflow**: Teacher switches between PDF tabs, crops from any PDF, attaches to any question

3. Add **Tab 3: "Pages for Grading"**:
   - Checklist of all QP pages with AI-suggested inclusions pre-checked
   - Each row shows: checkbox, page number, content summary, reason for inclusion
   - Bulk actions: [Select All] [Deselect Unused]
   - Estimated token count and cost impact display
   - "Confirm Pages" button saves `included_page_refs`

**Deliverable:** Can upload multi-page question paper PDF → AI extracts questions in background → teacher reviews in split-screen view → crops diagrams/images from PDF and attaches to questions → edits question text → confirms which pages to include in grading prompt. Also supports uploading additional PDFs (instructions, answer keys) as separate tabs for cropping reference.

---

### **Phase 5: ZIP Ingestion Pipeline**
**Complexity: ★★★★☆ | Estimated: 4-5 days**

**Backend Tasks:**
1. Install new deps: `pymupdf`, `pillow`, `jsonschema`
2. Create `backend/services/pdf_service.py`:
   - `rasterize_pdf_to_pngs(file, out_dir, dpi=150)` → page images
3. Create `backend/services/zip_service.py`:
   - Extract ZIP, find `*.pdf` entries
   - Parse filename `studentName_rollNo_class_section.pdf` → metadata
4. Create `backend/models/sheets.py` - AnswerSheet, SheetPage, UploadBatch models
5. Create `backend/routers/sheets.py`:
   - `POST /exams/{id}/sheets/upload-zip` - background task
   - Return `upload_batch_id` immediately
   - Track progress in `upload_batches` collection
6. Create `backend/routers/files.py`:
   - `GET /files/sheets/{id}/pages/{n}` - auth-checked image streaming
   - `GET /files/sheets/{id}/pdf`
7. Update `main.py` - mount new routers

**Frontend Tasks:**
1. Create upload state management (poll `upload_batches` status)
2. Create ZIP upload component with progress bar
3. Reuse existing polling hooks from current codebase

**Deliverable:** Upload ZIP → backend extracts PDFs → rasterizes to PNG page images → sheets in `pending_mapping` status

---

### **Phase 6: Mapping UI (Replicate Demo)**
**Complexity: ★★★★☆ | Estimated: 5-6 days**

**Frontend Tasks:**
1. Create `/exams/[id]/upload` page with 3-step wizard:
   - **Step 1**: Upload card (from Phase 5)
   - **Step 2**: Mapping one-by-one (main feature)
   - **Step 3**: Done (summary)

2. Mapping step components:
   - `Process PDF N/M` counter
   - Pre-filled form: student_name, roll_no, class (from filename)
   - Page thumbnails grid: `<Image unoptimized>` pointing to `/files/sheets/{id}/pages/{n}`
   - Zoom modal (reuse demo's pattern with React state)
   - Delete page button → `PATCH /sheets/{id}/pages/{page_no}`
   - **Save & Next** → `PATCH /sheets/{id}` status → `mapped`
   - **Skip** → status → `skipped`

3. Bottom "Saved Records" list:
   - Expandable rows showing page thumbnails
   - Edit button (re-open mapping for that sheet)
   - Delete button

**Backend Tasks:**
1. `PATCH /sheets/{id}` - update student mapping, status
2. `DELETE /sheets/{id}/pages/{page_no}` - set `is_deleted=true`
3. `POST /sheets/{id}/skip` - skip sheet

**Deliverable:** Teacher can map all PDFs one-by-one, delete wrong pages, save mapping

---

### **Phase 7: JSONL Builder + Draft Batch (Updated with QP Pages + Crop Attachments)**
**Complexity: ★★★★☆ | Estimated: 4-5 days**

**Backend Tasks:**
1. Create `backend/services/jsonl_service.py`:
   - `build_jsonl_line(sheet, answer_key, sample_sheets, schema)` → JSONL line
   - **NEW**: Includes question paper pages from `answer_key.included_page_refs`
   - **NEW**: Includes attached cropped images per question (`question.attached_images`)
   - **NEW**: Model selection based on `exam.complexity_tier`
   - JSONL uses **file paths** (not base64) for image references
   - `write_batch_input(batch_id, items)` → `storage/batches/{id}/input.jsonl`
   - `parse_batch_output(output_file)` → correlate results
2. Create `backend/models/batches.py` - BatchJob, BatchItem models
3. Create `backend/routers/batches.py`:
   - `POST /exams/{id}/batches` - build JSONL over all `mapped` sheets
   - Uses exam's complexity tier to select model
   - `GET /batches/{id}` - details + per-item list
   - `GET /batches/{id}/jsonl` - download input JSONL
   - `DELETE /batches/{id}/items/{item_id}` - remove from batch

**Frontend Tasks:**
1. Create `/exams/[id]/batches` page:
   - **Prepare JSONL** button → creates draft batch
   - Draft view: item count, model display (auto from complexity tier), **Download JSONL**
   - Model info: "Using gemini-2.5-flash (Standard complexity) — Est. $0.25/student"
   - Per-item list with delete button
   - **Submit to AI** button (goes to Phase 8)

**Deliverable:** Can build JSONL files from mapped sheets (with QP page references + attached cropped images), review before submission. Model auto-selected from exam complexity tier.

---

### **Phase 8: Batch Submit + File API Uploads + Provider Adapters + Poller**
**Complexity: ★★★★★ | Estimated: 6-7 days**

**Key Design Decision — Gemini File API (not inline base64):**
- The 20 MB per-request inline limit is too small for typical answer sheets (20+ pages)
- Solution: Upload all images to Gemini Files API during submit, reference by `file_uri` in JSONL
- Model/sample sheets: Upload once per exam, reuse URI across all student requests in a batch
- Student pages: Upload per batch during submit step
- Files expire after 48 hours — batch must complete before expiry

**Backend Tasks:**
1. Create `backend/services/batch_service.py`:
   ```
   upload_files_for_batch(input_jsonl_path, batch_id) → (uploaded_jsonl_path, [file_names])
   submit(provider, model, uploaded_jsonl_path) → provider_batch_id
   status(provider, provider_batch_id) → {status, completed, failed}
   download_output(provider, provider_batch_id, dest_path)
   cancel(provider, provider_batch_id)
   cleanup_expired_files(file_names)
   ```
2. Implement **Gemini Batch** adapter:
   - Use `google-genai` library for `files.upload()`, `batches.create()`, `batches.get()`
   - Upload images via Files API, get file URIs
   - Replace file paths in JSONL with `file_data` references using file URIs
   - Submit the modified JSONL to batch API
3. Implement **OpenAI Batch** adapter:
   - `/v1/files` upload, `/v1/batches` create
4. Create `backend/workers/batch_poller.py`:
   - Asyncio task, runs every `BATCH_POLL_INTERVAL_SEC` (default 300s)
   - Poll all `submitted`/`in_progress` batches
   - On completion: download output, parse, upsert `gradings`
5. Update `backend/routers/batches.py`:
   - Add `POST /batches/{id}/submit` — triggers file upload + batch submission
   - Returns progress events or status updates during file upload
   - Track uploaded file names in batch doc for expiry management
6. Update `backend/models/batches.py` — add `uploaded_file_names` field
7. Update `main.py` - start poller on `@app.on_event("startup")`

**Frontend Tasks:**
1. Update batches page submit flow:
   - Click "Submit to AI" → shows multi-step progress:
     - "Uploading images to Gemini (150/3000)..."
     - "Submitting batch..."
     - "Submitted"
   - Use SSE or polling for real-time upload progress
   - Submitted view: status badge, progress bar (`completed_count/item_count`)
   - `last_polled_at` display
   - Manual **Refresh** button → `POST /batches/{id}/refresh`
   - **Cancel** button (if provider allows)
2. Dashboard notification badge for batch completion

**Deliverable:** Can submit batches to Gemini (via File API) or OpenAI, background poller updates status, results ingested automatically. Supports 20+ pages per student without the 20 MB inline limit.

---

### **Phase 9: Grading Ingestion + Review UI + Override Log**
**Complexity: ★★★★☆ | Estimated: 5-6 days**

**Backend Tasks:**
1. Create `backend/services/grading_service.py`:
   - `validate_result_against_schema(result, schema_definition)` → jsonschema
   - `apply_to_mongo(grading_result, sheet_id)` → upsert `gradings`
2. Update `backend/routers/gradings.py`:
   - `GET /gradings/{id}` - auth: teacher/admin OR student (if published)
   - `PATCH /gradings/{id}` - teacher edits result, append to `override_log[]`
   - `POST /gradings/{id}/publish` - set status=published
3. Batch poller integration: on batch completion → validate → upsert grading

**Frontend Tasks:**
1. Create `/sheets/[id]` page:
   - **Left**: Page image carousel with zoom modal
   - **Right**: Dynamic form from `result_schema`:
     - Walk JSON-Schema recursively
     - Render fields based on type (string→input, number→input[type=number], array→repeatable rows)
     - For `questions` array: table with q_no, awarded, max, feedback, page_refs
   - **Save** button → `PATCH /gradings/{id}`
   - **Mark Reviewed** / **Mark Overridden** buttons
   - Audit log panel: show `override_log[]` entries

2. Create dynamic form renderer utility:
   - `walkSchema(schema)` → React components
   - Handle nested objects, arrays of objects

**Deliverable:** Teachers can review AI-graded results, edit marks, see audit trail

---

### **Phase 10: Publish Workflow + Student Portal**
**Complexity: ★★★☆☆ | Estimated: 3-4 days**

**Backend Tasks:**
1. Update `backend/routers/gradings.py`:
   - `POST /exams/{id}/publish-all` - bulk publish reviewed/overridden gradings
2. Update `backend/routers/sheets.py`:
   - `GET /students/me` - list published gradings for current student
   - Auth check: only show `status=published`

**Frontend Tasks:**
1. Update `/sheets/[id]` page:
   - **Publish** button (single sheet)
   - Disable editing after publish
2. Create `/exams/[id]/batches` page:
   - **Publish All** button (bulk)
   - Confirmation dialog
3. Create `/students/me` page:
   - Table of exams with published results only
   - Expandable rows: per-question breakdown (q_no, awarded, max, feedback)
   - Read-only view
   - Show total_awarded / total_max

**Deliverable:** Students can view their published grades, teachers can publish individually or in bulk

---

### **Phase 11: Polish**
**Complexity: ★★☆☆☆ | Estimated: 2-3 days**

**Tasks:**
1. Add skeleton loaders for all pages
2. Add error boundaries (React error boundary component)
3. Dashboard notification badges (batches in progress, pending review)
4. Bulk actions: bulk delete sheets, bulk re-process
5. Responsive design checks (mobile/tablet)
6. Loading states for all async operations
7. Toast notifications for success/error
8. Confirmation dialogs for destructive actions
9. Extraction error recovery UI (retry with same file, upload different file)

**Deliverable:** Production-ready, polished UI

---

### **Phase 12: Exam-Student Enrollment + Answer Sheet Matching**
**Complexity: ★★★★☆ | Estimated: 6-7 days**

This phase introduces a separate `exam_students` collection to explicitly link students to exams (via their class enrollment), then provides auto-match (bulk) and manual-match UIs to connect uploaded answer sheets to those enrolled students, and finally propagates `student_id` to grading records so students can view their own results.

#### **Backend Tasks:**

1. **`exam_students` Collection (Soft-Delete Enrollment Model)**
   - Add `exam_students` collection in `backend/db/database.py`
   - Schema: `{ _id, exam_id, student_id, enrolled_at, status: "active" | "removed", removed_at }`
   - Create compound unique index on `{exam_id, student_id}`
   - Create indexes on `exam_id` and `student_id` separately for efficient queries

2. **Auto-Populate on Exam Creation**
   - When exam is created with a `class_id`, query all active students in that class
   - Insert one `exam_students` record per student with `status: "active"`
   - If exam's class is changed, remove old enrollments (set `status: "removed"`) and populate new ones

3. **"Sync Students" Endpoint**
   - `POST /exams/{id}/sync-students` — compares class enrollment with `exam_students`
   - Adds new students (newly added to class) as `active`
   - Marks removed students (deleted from class) as `removed` (soft delete)
   - Returns `{ added_count, removed_count, total_active }`

4. **Exam-Student List Endpoints**
   - `GET /exams/{id}/students/` — list enrolled students with status
   - `GET /exams/{id}/students/summary/` — counts: active, removed, mapped sheets, unmapped sheets

5. **Auto-Match Service (Bulk)**
   - `POST /exams/{id}/sheets/auto-match` — matches pending sheets to enrolled students
   - Matching priority: exact `roll_no` match → fuzzy `student_name` match within exam's class
   - Returns list of proposed matches with confidence scores
   - Accepts `confirm: true` to apply all matches (updates `answer_sheets.student_id` and `status: "mapped"`)
   - Does NOT delete unmatched sheets — they remain `pending_mapping`

6. **Manual Match Enhancement**
   - Extend `PATCH /sheets/{id}` to accept `student_id` in the mapping body
   - When `student_id` is set, validate it exists in `exam_students` for this exam
   - Update sheet `status` to `"mapped"`

7. **Student ID Propagation to Gradings**
   - Add `student_id` field to `gradings` collection (optional, for backward compatibility)
   - When grading is upserted (in `grading_service.py`), look up `answer_sheets.student_id` and copy it to the grading doc
   - When `upsert_grading` runs, query the answer sheet and populate `student_id` if available

8. **Fix Student Results Endpoint**
   - Fix `/students/me/gradings/` to query by `student_id` in gradings (instead of broken `sheet_id == user.id` logic)
   - Only return gradings with `status: "published"` for the current student
   - Enrich response with exam title, subject name (already partially implemented)

9. **Exam Creation/Update Router Changes**
   - `POST /exams` — after creating exam, auto-populate `exam_students`
   - `PATCH /exams/{id}` — if `class_id` changes, trigger re-sync of enrollments
   - `POST /exams/{id}/sync-students` — manual sync endpoint

#### **Frontend Tasks:**

1. **Exam Students Tab (on `/exams/[id]` page)**
   - New tab: "Enrolled Students"
   - Shows table of students from the exam's class with columns: Name, Roll No, Status (active/removed)
   - **"Sync Students" button** — triggers POST to sync endpoint, shows toast with added/removed counts
   - Filter toggle: Show All / Active Only / Removed Only
   - Student count badges at top: Active, Removed, Mapped Sheets, Unmapped Sheets

2. **Mapping Step UI Enhancements (on `/exams/[id]/upload`)**
   - **Auto-Match Button** — appears at top of MappingStep when pending sheets exist
     - Opens a modal showing proposed matches: PDF filename | Parsed Name/Roll | → Matched Student (name, roll) | Confidence
     - Checkboxes to select which matches to apply (default: all)
     - "Apply Selected" button confirms matches
     - Unmatched sheets remain in pending list
   - **Student Lookup Dropdown** — in the existing mapping form, next to the Roll No field
     - Searchable dropdown of enrolled students for this exam
     - Selecting a student auto-fills name, roll, class AND sets `student_id`
     - Falls back to manual entry if student not found in the list

3. **New Page: `/exams/[id]/assign-results` (Post-Grading Assignment)**
   - Table of all graded sheets with columns: Sheet ID, Student Name (from sheet), Roll No, Grading Status, Assigned Student
   - Filter: Unassigned Only / All
   - Bulk action: Select multiple → "Assign to Student" modal with searchable dropdown
   - Individual row: Dropdown to assign/reassign a student
   - Shows unmatched sheets that got graded (for review)

4. **Student Results Page Fix (`/students/me`)**
   - Fix the data fetching to use the corrected backend endpoint
   - Results now properly display per-student via `student_id` lookup
   - Shows question-level breakdown as before (already implemented)

#### **Data Flow for Matching:**

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Exam Created → Auto-populate exam_students from class        │
│    exam_students: [{exam_id, student_id: S1, status: active},   │
│                    {exam_id, student_id: S2, status: active}]   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. ZIP Uploaded → Sheets in pending_mapping                     │
│    answer_sheets: [{student_name: "Raj", roll_no: "23",          │
│                     student_id: null, status: pending_mapping}]  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. Auto-Match or Manual Match                                   │
│    Auto: roll_no "23" → find student with roll_no "23" in       │
│          exam_students → set student_id = S1                    │
│    Manual: Teacher selects "Raj Kumar (Roll 23)" from dropdown  │
│            → set student_id = S1                                │
│    answer_sheets: [..., student_id: S1, status: mapped]         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. AI Grading → Grading created with student_id copied          │
│    gradings: [{sheet_id, exam_id, student_id: S1,               │
│                result: {..., total_awarded: 45, total_max: 60}}]│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. Publish → Student S1 can view results                        │
│    GET /students/me/gradings → WHERE student_id = S1            │
│                              AND status = published             │
└─────────────────────────────────────────────────────────────────┘
```

#### **Backward Compatibility:**
- Existing exams without `exam_students` records continue to work
- Auto-match gracefully handles exams with no enrolled students (returns empty matches)
- `student_id` in gradings is optional — existing gradings without it are unaffected
- Old answer sheets without `student_id` can still be graded and published

**Deliverable:** Students are explicitly enrolled in exams via class sync. Answer sheets can be auto-matched (bulk by roll number) or manually matched to enrolled students. Grading results carry `student_id` linkage. Students can correctly view their published results.

---

### **Phase 13: Polish**
**Complexity: ★★☆☆☆ | Estimated: 2-3 days**

**Tasks:**
1. Add skeleton loaders for all pages
2. Add error boundaries (React error boundary component)
3. Dashboard notification badges (batches in progress, pending review)
4. Bulk actions: bulk delete sheets, bulk re-process
5. Responsive design checks (mobile/tablet)
6. Loading states for all async operations
7. Toast notifications for success/error
8. Confirmation dialogs for destructive actions
9. Extraction error recovery UI (retry with same file, upload different file)

**Deliverable:** Production-ready, polished UI

---

## Project Management Task Breakdown

| Epic | Task | Depends On |
|------|------|------------|
| **Epic 1: Foundation** | Task 1.1: Auth backend | None |
| | Task 1.2: Auth frontend + middleware | 1.1 |
| **Epic 2: School Setup** | Task 2.1: Users CRUD | 1.2 |
| | Task 2.2: Classes/Subjects | 1.2 |
| **Epic 3: Exam Setup** | Task 3.1: Exams + Complexity + Answer Keys | 2.2 |
| | Task 3.2: Result Schemas | 3.1 |
| **Epic 3.5: QP Extraction** | Task 3.5.1: Question paper upload + extraction backend | 3.1 |
| | Task 3.5.2: Extraction worker + progress polling | 3.5.1 |
| | Task 3.5.3: Split-screen review UI with pdf.js viewer | 3.5.2 |
| | Task 3.5.4: Canvas crop overlay + active question state | 3.5.3 |
| | Task 3.5.5: Crop-to-attach popup + image upload endpoint | 3.5.4 |
| | Task 3.5.6: Multi-PDF tab support + additional PDF upload | 3.5.3 |
| | Task 3.5.7: Page inclusion checklist + confirm pages | 3.5.3 |
| **Epic 4: Upload & Mapping** | Task 4.1: ZIP ingestion pipeline | 3.1 |
| | Task 4.2: Mapping UI | 4.1 |
| **Epic 5: AI Grading** | Task 5.1: JSONL builder (with QP pages + crop attachments) | 4.2 + 3.5.7 |
| | Task 5.2: Batch submit + poller | 5.1 |
| **Epic 6: Review & Publish** | Task 6.1: Grading review UI | 5.2 |
| | Task 6.2: Publish + Student portal | 6.1 |
| **Epic 7: Enrollment & Matching** | Task 7.1: exam_students collection + auto-populate | 3.1 (Exams) + 2.2 (Students) |
| | Task 7.2: Sync students + enrollment endpoints | 7.1 |
| | Task 7.3: Auto-match service (bulk roll_no matching) | 7.1 + 4.1 (ZIP pipeline) |
| | Task 7.4: Manual match UI enhancements (dropdown + modal) | 7.3 + 4.2 (Mapping UI) |
| | Task 7.5: student_id propagation to gradings | 7.4 + 5.2 (Grading) |
| | Task 7.6: Fix student results endpoint | 7.5 + 6.2 (Student portal) |
| | Task 7.7: Post-grading assignment page | 7.5 |
| **Epic 8: Polish** | Task 8.1: UI polish + error handling | 7.7 |

---

## Critical Path (Must Do In Order)

```
Phase 1 (Auth) → Phase 2 (Users/Classes) → Phase 3 (Exams/Keys/Complexity)
                                                ↓
                                     Phase 4 (QP Extraction + Split-Screen Review + Crop-to-Attach)
                                                ↓
                                     Phase 5 (ZIP Upload) → Phase 6 (Mapping)
                                                ↓
                                     Phase 7 (JSONL with QP pages + crops) → Phase 8 (Batch Submit)
                                                ↓
                                     Phase 9 (Review) → Phase 10 (Publish)
                                                ↓
                                     Phase 12 (Enrollment + Matching) — can run parallel with 11
                                     ├── 12.1: exam_students collection + auto-populate
                                     ├── 12.2: Sync students + endpoints
                                     ├── 12.3: Auto-match service
                                     ├── 12.4: Manual match UI
                                     ├── 12.5: student_id in gradings
                                     ├── 12.6: Fix student results
                                     └── 12.7: Post-grading assignment page
                                                ↓
                                     Phase 13 (Polish)
```

Skipping any phase blocks the next. You **cannot** test end-to-end without completing Phase 1 first.

Phase 12 depends on: Phases 2 (students), 3 (exams), 5 (ZIP pipeline), 6 (mapping UI), 9 (grading). It can be developed in parallel with Phase 11 (minor polish items) but must complete before Phase 13 (final polish).

---

## Complexity Ratings Summary

| Phase | Feature | Complexity (1-5) |
|-------|---------|------------------|
| 1 | Auth core + password reset | ★★★☆☆ |
| 2 | Users/Classes/Subjects CRUD | ★★☆☆☆ |
| 3 | Exams + Complexity + Keys + Schemas | ★★★☆☆ |
| 4 | QP Upload + AI Extraction + Split-Screen Review + Crop-to-Attach | ★★★★★ |
| 5 | ZIP ingestion pipeline | ★★★★☆ |
| 6 | Mapping UI | ★★★★☆ |
| 7 | JSONL builder + QP pages + crop attachments | ★★★★☆ |
| 8 | Batch submit + poller | ★★★★★ |
| 9 | Grading ingestion + review UI | ★★★★☆ |
| 10 | Publish + Student portal | ★★★☆☆ |
| 12 | Exam-Student Enrollment + Matching + Grading linkage | ★★★★☆ |
| 13 | Polish | ★★☆☆☆ |

---

## Key Notes
- All phases should be tested independently before moving to the next.
- Frontend must follow Next.js 16 App Router patterns (read `node_modules/next/dist/docs/` before coding).
- Backend uses Motor (async MongoDB) and FastAPI with async endpoints.
- UI styling must match `workflow_diagram.html` (dark theme, CSS variables from Section 2 of answer_sheet_management_plan.md).
- Phase 8 (Batch Submit + File API + Poller) has the highest complexity due to provider abstraction, file upload pipeline, and async polling.
- Phase 4 (QP Extraction + Split-Screen Review + Crop-to-Attach) is the second-highest complexity: async two-pass AI extraction, progress polling, pdf.js viewer with canvas cropping, multi-PDF tab switching, and image attachment pipeline.
- Phase 12 (Exam-Student Enrollment + Matching) is also high complexity: new collection with soft deletes, auto-populate from class, sync endpoint, bulk auto-match service with confidence scoring, manual match UI with searchable dropdown, grading student_id propagation, and fixing broken student results endpoint.
- **Crop-to-attach replaces auto page references**: Instead of linking questions to full QP pages, teachers actively crop diagram/image regions and attach them to specific questions. This produces cleaner JSONL prompts with only relevant visual context.
- **Attached images in JSONL**: Each question with attached crops includes those images as `_file_ref` entries in the JSONL. Questions without crops fall back to full page references.
- Refer to Section 14 of `answer_sheet_management_plan.md` for full difficulties/conflicts analysis.

---

## Important Note: Gemini File API Upload Approach (Phase 8)

This section documents the File API approach adopted to bypass the Gemini batch API's **20 MB per-request inline limit**. Without this, a student with 20+ answer pages would exceed the limit and fail.

### File Storage: Two Locations

| Location | What's Stored | Lifetime |
|----------|---------------|----------|
| **Local filesystem** (`storage/answer_sheets/{sheet_id}/page_001.png`) | Rasterized page images from student PDFs | Permanent — source of truth |
| **Local filesystem** (`storage/question_papers/{exam_id}/page_001.png`) | Rasterized question paper pages | Permanent — source of truth |
| **Gemini Cloud** (`files/xxxxxxxxxxxx`) | Same images uploaded via Gemini Files API | Temporary — expires after **48 hours** |

### How URLs Are Linked to Students, QP Pages, and Model Sheets

**Draft JSONL (Phase 7 — built during batch creation):**

One JSONL line per student, containing **local file paths** (not URLs):

```json
{
  "key": "sheet_67abc123def456",
  "request": {
    "contents": [{
      "role": "user",
      "parts": [
        {"text": "You are grading a handwritten answer sheet..."},
        {"text": "Student: Raj Kumar | Roll: 23 | Class: 10-A"},
        {"_file_ref": "storage/question_papers/exam_001/page_001.png"},
        {"_file_ref": "storage/question_papers/exam_001/page_006.png"},
        {"_file_ref": "storage/samples/exam_001/sample_page_1.png"},
        {"_file_ref": "storage/answer_sheets/67abc123def456/page_001.png"},
        {"_file_ref": "storage/answer_sheets/67abc123def456/page_002.png"},
        {"text": "Respond with JSON matching schema: {...}"}
      ]
    }]
  }
}
```

Key observations:
- **`key`** = `sheet_{sheet_id}` — unique per student, used to correlate results back
- **QP pages** (`_file_ref` → `storage/question_papers/exam_001/...`) — shared across ALL students, only teacher-confirmed pages included
- **Model sheets** (`_file_ref` → `storage/samples/exam_001/...`) — shared across ALL students in this batch
- **Student pages** (`_file_ref` → `storage/answer_sheets/{sheet_id}/page_XXX.png`) — unique per student

### Upload Phase (during `POST /batches/{id}/submit`)

`batch_service.upload_files_for_batch()` processes the draft JSONL:

1. **Scan all `_file_ref` entries** across all student lines
2. **Deduplicate** — if `sample_page_1.png` is referenced by 50 students, it's uploaded **once**
3. **Upload each unique image** to Gemini Files API → returns file name (e.g., `files/abc123`)
4. **Build URI mapping table**:

```python
file_uri_map = {
    "storage/question_papers/exam_001/page_001.png": "files/qp001",
    "storage/question_papers/exam_001/page_006.png": "files/qp006",
    "storage/samples/exam_001/sample_page_1.png": "files/abc123",
    "storage/answer_sheets/67abc123def456/page_001.png": "files/ghi789",
    "storage/answer_sheets/67abc123def456/page_002.png": "files/jkl012",
}
```

5. **Replace `_file_ref` with `file_data`** in every student line:

```json
{"file_data": {"mime_type": "image/png", "file_uri": "files/abc123"}}
```

6. **Write final JSONL** to `storage/batches/{batch_id}/input_with_uris.jsonl`
7. **Store uploaded file names** in `batch_jobs.uploaded_gemini_files` for expiry tracking

### Complete Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 7: Build Draft JSONL                                              │
│                                                                         │
│  For each mapped sheet (student):                                       │
│    1. Read sheet metadata (name, roll, class)                           │
│    2. Read sheet page images from local storage                         │
│    3. Read QP pages from answer_key.included_page_refs                  │
│    4. Read model answer images from local storage                       │
│    5. Build JSONL line with _file_ref pointing to LOCAL paths           │
│    6. Write to storage/batches/{batch_id}/input.jsonl                   │
│                                                                         │
│  Result: Draft JSONL with local file paths (no Gemini involvement yet)  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 8: Submit (File API Upload + Batch Creation)                      │
│                                                                         │
│  Step A: Scan all _file_ref across ALL student lines                    │
│          → Collect unique file paths                                    │
│          Example: 50 students × 20 pages = 1000 student page refs       │
│                   + 10 QP page refs = 10 shared across all students     │
│                   + 10 model page refs = 10 shared across all students  │
│                   = 1020 unique paths                                   │
│                                                                         │
│  Step B: Upload each unique image to Gemini Files API                   │
│          storage/question_papers/exam_001/page_001.png → files/qp001    │
│          storage/samples/exam_001/sample_page_1.png  →  files/abc123    │
│          storage/answer_sheets/sheet001/page_001.png →  files/ghi789    │
│          → Progress: "Uploading 150/1020 images..."                     │
│                                                                         │
│  Step C: Replace _file_ref with file_data URIs in each student line     │
│          Student 67abc... gets: files/qp001 (QP) + files/ghi789...      │
│          Student 67def... gets: files/qp001 (QP) + files/jkl012...      │
│          (QP pages + model sheets shared via same URI, student pages unique) │
│                                                                         │
│  Step D: Write input_with_uris.jsonl                                    │
│                                                                         │
│  Step E: Upload input_with_uris.jsonl to Gemini Files API               │
│          → files/batch_input_xyz                                        │
│                                                                         │
│  Step F: Create batch job                                               │
│          client.batches.create(model="gemini-2.5-flash",                │
│                                 src="files/batch_input_xyz")            │
│          → batches/zzz999                                               │
│                                                                         │
│  Step G: Update batch_jobs in MongoDB                                   │
│          status = "submitted"                                           │
│          provider_batch_id = "batches/zzz999"                           │
│          uploaded_gemini_files = ["files/qp001", "files/abc123", ...]   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ POLLER: Monitor & Ingest Results (every 5 min)                          │
│                                                                         │
│  1. Poll batches/zzz999 → status: JOB_STATE_SUCCEEDED                   │
│  2. Download output from Gemini → storage/batches/{id}/output.jsonl     │
│  3. Parse output JSONL:                                                 │
│     {"key": "sheet_67abc123def456", "response": {"candidates": [...]}}  │
│  4. Match key → batch_items → sheet_id                                  │
│  5. Validate result against exam's result_schema                        │
│  6. Upsert to gradings collection                                       │
│  7. Update sheet status = "graded"                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Design Points

1. **One upload per unique image**: QP pages and model sheets are uploaded **once** and the same URI is used in all student lines.

2. **Correlation is by `key`**: The `key` field (`sheet_{sheet_id}`) in each JSONL line is preserved in the output. The poller uses it to match results back to the correct student.

3. **Local files are never deleted**: The Gemini uploads are temporary copies. The original page images remain in `storage/` forever.

4. **File expiry is tracked**: `batch_jobs.uploaded_gemini_files` stores all Gemini file names. If a batch is cancelled and needs re-submission, these files may have expired and must be re-uploaded.

5. **Why this approach**: The Gemini batch API has a **20 MB per-request inline limit**. A student with 20 answer pages + 10 model pages at ~1 MB each would total ~30 MB — exceeding the limit. The File API removes this constraint (each file can be up to 2 GB).

6. **UX during submit**: The submit button shows multi-step progress:
   - "Uploading QP pages to Gemini (10/10)..."
   - "Uploading model sheets to Gemini (3/10)..."
   - "Uploading student pages (150/3000)..."
   - "Submitting batch..."
   - "Submitted"
