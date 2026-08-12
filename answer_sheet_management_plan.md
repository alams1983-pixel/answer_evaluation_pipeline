# Answer Sheet Management - Implementation Plan

## 1. Goal

Extend the existing AI PDF processing app (FastAPI + Next.js 16 + MongoDB) into a school/institute management tool that emulates a physical answer-sheet checking workflow for a teacher. Teachers upload a ZIP of student PDFs, the backend splits each PDF into page images, the teacher maps each PDF to a student record and (optionally) attaches a sample answer sheet / answer key to guide the AI. For each mapped sheet a JSONL request line is built; the batch is reviewed, then submitted to the LLM **Batch API** (Gemini / OpenAI). Because batch jobs may take 24–48 h, the system tracks batch state, ingests results when ready, and publishes marks to students only after a teacher reviews them.

The system supports two answer key workflows:
- **Simple papers**: Manual question entry (existing flow)
- **Complex papers (multi-page, diagrams, images)**: Upload question paper PDF → AI extracts questions → teacher reviews and confirms → system builds grading prompt with relevant pages

## 2. Demo HTML Logic (summary of `answer_sheet_management_demo.html`)

The demo is a pure client-side prototype:
1. User uploads a ZIP via `<input id="zipInput">`.
2. JSZip loads the archive; every `*.pdf` entry is collected and sorted alphabetically.
3. PDFs are processed one at a time (`processNextPDF`):
   - pdf.js renders every page to a canvas (scale 1.5) → base64 PNG data URLs stored in `currentImages`.
   - Filename convention `studentName_rollNo_class_section.pdf` pre-fills the form fields.
4. Teacher can click any page to zoom (modal), click `✖` to delete a wrong/blank page, then **Save Record & Next** which pushes `{ student_name, roll_no, class, answer_sheet: [dataURLs] }` into `records` and moves to the next PDF, or **Skip**.
5. Saved records list supports expand/edit, per-page deletion, per-record download and bulk "Download JSON".

The target of that JSON is to become a **JSONL batch file** sent to an AI vision batch API for evaluation. The plan below keeps the same per-sheet UX but moves persistence to the backend, adds auth/RBAC, treats the Batch API as the sole grading path, supports dynamic result schemas, and adds sample-answer-sheet guidance.

## UI Styling Guidelines (must match workflow_diagram.html)

The UI must replicate the dark theme and visual style of `workflow_diagram.html`. Update `frontend/src/app/globals.css` to use these CSS variables and component styles:

### CSS Variables (add to `:root`)
```css
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #22263a;
  --border: #2e3350;
  --accent: #4f8ef7;
  --accent2: #7c5cfc;
  --green: #22c55e;
  --yellow: #f59e0b;
  --red: #ef4444;
  --orange: #f97316;
  --teal: #14b8a6;
  --pink: #ec4899;
  --text: #e2e8f0;
  --muted: #94a3b8;
  --radius: 10px;
  --font-sans: 'Segoe UI', system-ui, -apple-system, sans-serif;
}
```

### Component Classes to Create
- `.section-header` — flex row with title, line, badge
- `.section-badge` — rounded pill badge (accent2 background)
- `.card` / `.glass-panel` — surface background, border, radius
- `.node` — inline-flex status nodes with color variants:
  - `.node-blue` — rgba(79,142,247,.15) border + #7db4ff text
  - `.node-green` — rgba(34,197,94,.12) border + #4ade80 text
  - `.node-yellow` — rgba(245,158,11,.12) border + #fcd34d text
  - `.node-red` — rgba(239,68,68,.12) border + #fca5a5 text
  - `.node-purple` — rgba(124,92,252,.15) border + #a78bfa text
  - `.node-teal` — rgba(20,184,166,.12) border + #5eead4 text
  - `.node-orange` — rgba(249,115,22,.12) border + #fdba74 text
- `.status-badge` — small rounded pill for status (use `.s-pending`, `.s-mapped`, etc.)
- `.btn-primary` — accent gradient button
- `.arrow` — muted arrow separator
- `.arch-grid` — 3-column grid for architecture diagrams
- `.flow-swimlane` — grid with lane-label + lane-content for workflow steps
- `.state-machine` — flex wrap for state transitions
- `.erd` — grid of ERD table cards
- `.rbac-table` — full-width table with styled headers

### Font & Body
```css
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.5;
}
```

### Migration Note
The existing `globals.css` uses different variable names (`--bg-primary`, `--accent-primary`, etc.). Either:
1. Replace the existing variables with the new ones above, OR
2. Add the new variables and create aliases: `--bg: var(--bg-primary)`, etc.

**Recommended**: Replace entirely to match workflow_diagram.html exactly.

## 3. High-level Architecture

```
Next.js 16 (App Router)
   └── /login, /register, /forgot-password, /reset-password/
   └── /dashboard (role-aware)
   └── /classes, /subjects, /exams          (admin/teacher)
   └── /exams/[id]/answer-key               (Upload QP → AI extraction → Review questions → Confirm pages)
   └── /exams/[id]/upload                   (ZIP upload wizard — mirrors demo)
   └── /exams/[id]/sheets                   (mapping + JSONL preview)
   └── /exams/[id]/batches                  (batch lifecycle UI + model selection by exam complexity)
   └── /sheets/[id]                         (page viewer + review graded marks)
   └── /students/me                         (own published results)

FastAPI
   └── /auth/*           (register-by-admin, login, me, forgot, reset, email verification)
   └── /users, /classes, /subjects, /exams, /answer-keys
   └── /question-papers/* (upload, extract, status, pages, review)
   └── /sheets/*         (upload ZIP, list, pages CRUD, jsonl preview)
   └── /batches/*        (build, review, submit, poll, ingest, cancel)
   └── /gradings/*       (review, override, publish)
   └── /files/*          (auth-checked image / pdf / jsonl streaming)

MongoDB (motor, same instance)
   └── users, password_resets, classes, subjects, enrollments,
       exams, answer_keys, question_papers, extraction_tasks,
       answer_sheets, sheet_pages, result_schemas,
       batch_jobs, batch_items, gradings

Filesystem
   storage/
     original_pdfs/{sheet_id}.pdf
     answer_sheets/{sheet_id}/page_XXX.png
     question_papers/{exam_id}/page_XXX.png    # NEW: rasterized QP pages
     answer_keys/{exam_id}/key.pdf
     samples/{exam_id}/sample_XX.pdf
     batches/{batch_id}/input.jsonl
     batches/{batch_id}/output.jsonl
```

## 4. Authentication & RBAC

- **Library**: `passlib[bcrypt]` + `python-jose[cryptography]` + `python-multipart`.
- **User creation**: **only Admin or Teacher** can create / import users. No public self-registration. A one-time bootstrap script (or first-run check) seeds the initial admin from env vars (`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`).
- **Endpoints**:
  - `POST /auth/login` → JWT (24 h).
  - `GET /auth/me`.
  - `POST /auth/forgot-password` → generates a one-time reset token stored in `password_resets` (hashed, 30 min TTL). Token is returned in API response in dev; in production it can be delivered via an external channel (out of scope — **no email verification / email sending**). UI shows the token for admins to hand to the user or the user clicks a deep link.
  - `POST /auth/reset-password` → body `{token, new_password}` → rotates hash, invalidates token.
  - `POST /auth/change-password` (authenticated).
- **Tokens**: JWT with `sub`, `role`, `exp`. Stored in `localStorage` with `Authorization: Bearer` header (simple).
- **FastAPI deps**: `get_current_user`, `require_roles("admin","teacher")`.
- **RBAC matrix**:

| Action                                    | Admin | Teacher | Student |
|-------------------------------------------|:-----:|:-------:|:-------:|
| Create/import users, classes, subjects    |  ✅   |   ✅*   |   ❌    |
| Create exams, answer keys, sample sheets  |  ✅   | own classes | ❌ |
| Upload question paper, run extraction     |  ✅   | own exams | ❌ |
| Upload ZIP, map sheets, build JSONL       |  ✅   | own exams | ❌ |
| Submit / cancel batch jobs                |  ✅   | own exams | ❌ |
| Review & override gradings, publish       |  ✅   | own exams | ❌ |
| View own **published** results            |  ✅   |   ✅    |   ✅    |

*Teachers may create students and classes they own; managing other teachers/admins is admin-only.

## 5. Database Schema (MongoDB collections)

### 5.1 `users`
```json
{
  "_id": ObjectId,
  "email": "teacher1@school.edu",
  "password_hash": "bcrypt...",
  "full_name": "Jane Doe",
  "role": "admin" | "teacher" | "student",
  "roll_no": "23",
  "class_id": ObjectId | null,
  "is_active": true,
  "created_by": ObjectId,
  "created_at": ISODate,
  "updated_at": ISODate
}
```
Indexes: unique `email`; unique sparse `(class_id, roll_no)`.

### 5.2 `password_resets`
```json
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "token_hash": "sha256...",
  "expires_at": ISODate,           // TTL index
  "used_at": ISODate | null,
  "created_at": ISODate
}
```

### 5.3 `classes`
```json
{ "_id": ObjectId, "name": "Grade 10-A", "academic_year": "2025-26",
  "teacher_ids": [ObjectId], "created_by": ObjectId, "created_at": ISODate }
```

### 5.4 `subjects`
```json
{ "_id": ObjectId, "name": "Physics", "code": "PHY", "class_id": ObjectId,
  "teacher_ids": [ObjectId], "created_at": ISODate }
```

### 5.5 `exams` (UPDATED — added complexity_tier)
```json
{
  "_id": ObjectId,
  "title": "Mid-term Physics",
  "subject_id": ObjectId,
  "class_id": ObjectId,
  "total_marks": 100,
  "scheduled_on": ISODate,
  "answer_key_id": ObjectId | null,
  "result_schema_id": ObjectId | null,
  "complexity_tier": "simple" | "standard" | "complex",   // NEW: exam-level complexity
  "grading_rubric": "strict" | "lenient" | "custom",
  "rubric_notes": "string",
  "status": "draft" | "ready" | "grading" | "partially_graded" | "completed",
  "created_by": ObjectId,
  "created_at": ISODate
}
```

### 5.6 `question_papers` (NEW)
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "source_file": "storage/question_papers/{exam_id}/original.pdf",
  "total_pages": 25,
  "pages": [
    {
      "page_no": 1,
      "image_path": "storage/question_papers/{exam_id}/page_001.png",
      "is_instruction_page": true,
      "has_questions": false,
      "has_diagrams": false,
      "is_needed_for_grading": true,
      "reason": "General instructions"
    },
    {
      "page_no": 6,
      "image_path": "storage/question_papers/{exam_id}/page_006.png",
      "is_instruction_page": false,
      "has_questions": true,
      "has_diagrams": true,
      "is_needed_for_grading": true,
      "reason": "Contains Q11 with circuit diagram"
    }
  ],
  "extracted_questions": [
    {
      "q_no": "11",
      "question": "Analyze the circuit diagram and calculate current...",
      "question_page_refs": [6],
      "expected_answer": "",
      "expected_answer_source": null,
      "marks": 5,
      "keywords": ["circuit", "current", "voltage"],
      "marking_scheme": "2 marks for formula, 3 for calculation",
      "marking_scheme_page_ref": 6,
      "has_diagram": true,
      "diagram_page_refs": [6]
    },
    {
      "q_no": "12",
      "question": "Interpret the velocity-time graph...",
      "question_page_refs": [7, 8],
      "expected_answer": "Slope = acceleration = 2 m/s². Area = displacement = 50m.",
      "expected_answer_source": "model_answer_doc",
      "marks": 8,
      "keywords": ["slope", "acceleration", "area", "displacement"],
      "marking_scheme": "3 marks for slope calculation, 3 for area, 2 for units",
      "marking_scheme_page_ref": 7,
      "has_diagram": true,
      "diagram_page_refs": [7, 8]
    }
  ],
  "status": "pending_extraction" | "extracted" | "reviewed",
  "extraction_model": "gemini-2.0-flash",
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 5.8 `extraction_tasks` (NEW — tracks async extraction progress)
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "status": "pending" | "rasterizing" | "analyzing" | "consolidating" | "completed" | "failed",
  "total_pages": 25,
  "processed_pages": 18,
  "current_page": 19,
  "current_step": "Analyzing page 19 of 25...",
  "questions_found_so_far": 15,
  "error": null,
  "started_at": ISODate,
  "completed_at": ISODate | null
}
```
Indexes: unique `exam_id`, TTL on `completed_at` (auto-cleanup after 24h).

### 5.8a `question_paper_crops` (NEW — cropped image attachments per question)
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "question_paper_id": ObjectId,
  "question_index": 0,
  "q_no": "11",
  "image_path": "storage/question_papers/{exam_id}/crops/q11_diagram_001.png",
  "source_pdf": "original.pdf",
  "page_no": 6,
  "bbox": { "x": 120, "y": 340, "width": 400, "height": 280 },
  "created_at": ISODate
}
```
Indexes: `(exam_id, question_paper_id, question_index)`.

### 5.8b `additional_pdfs` (NEW — supplementary PDFs per exam)
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "source_file": "storage/question_papers/{exam_id}/additional/instructions.pdf",
  "label": "General Instructions",
  "type": "instructions" | "answer_key" | "reference",
  "total_pages": 3,
  "created_at": ISODate
}
```

### 5.9 `answer_keys` (UPDATED — added QP references, page inclusion, model answers)
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "questions": [
    {
      "q_no": "1a",
      "question": "...",
      "question_page_refs": [2],
      "expected_answer": "Newton's first law: object at rest stays at rest...",
      "expected_answer_source": "teacher_typed" | "ai_extracted" | null,
      "marks": 5,
      "keywords": ["..."],
      "marking_scheme": "...",
      "marking_scheme_page_ref": 2,
      "has_diagram": false,
      "diagram_page_refs": [],
      "attached_images": [
        { "url": "storage/question_papers/{exam_id}/crops/q11_diagram_001.png",
          "source_pdf": "original.pdf",
          "page_no": 6,
          "bbox": { "x": 120, "y": 340, "width": 400, "height": 280 },
          "label": "circuit diagram" }
      ]
    }
  ],
  "question_paper_id": ObjectId | null,              // NEW: linked QP
  "included_page_refs": [1, 2, 3, 5, 6, 7, 8],       // NEW: teacher-confirmed pages
  "excluded_page_refs": [4, 9, 10],                   // NEW: teacher-excluded pages
  "sample_sheets": [
    { "kind": "pdf" | "text" | "image",
      "path": "storage/samples/{exam_id}/sample_01.pdf",
      "label": "Model answer (full marks)",
      "notes": "..." }
  ],
  "source": "manual" | "ai_extracted" | "hybrid" | "reference_only",
  "source_file": "storage/answer_keys/{exam_id}/key.pdf" | null,
  "extraction_status": "none" | "pending" | "completed" | "failed",
  "created_at": ISODate
}
```

### 5.10 `answer_sheets`
One per student per exam.
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "subject_id": ObjectId,
  "student_id": ObjectId | null,
  "student_name": "Raj Kumar",
  "roll_no": "23",
  "class_label": "10-A",
  "original_filename": "Raj_23_10A.pdf",
  "original_pdf_path": "storage/original_pdfs/{sheet_id}.pdf",
  "page_count": 6,
  "status": "pending_mapping" | "mapped" | "jsonl_ready" | "in_batch"
          | "graded" | "reviewed" | "published" | "skipped" | "failed",
  "current_batch_id": ObjectId | null,
  "uploaded_by": ObjectId,
  "batch_upload_id": ObjectId,
  "created_at": ISODate,
  "updated_at": ISODate
}
```

### 5.11 `sheet_pages`
```json
{
  "_id": ObjectId, "sheet_id": ObjectId, "page_no": 1,
  "image_path": "storage/answer_sheets/{sheet_id}/page_001.png",
  "width": 1240, "height": 1754, "is_deleted": false, "created_at": ISODate
}
```

### 5.12 `upload_batches` (ZIP ingestion progress)
```json
{ "_id": ObjectId, "exam_id": ObjectId, "uploaded_by": ObjectId,
  "zip_filename": "...", "total_pdfs": 42, "processed_pdfs": 30,
  "status": "extracting" | "ready_for_mapping" | "completed" | "failed",
  "created_at": ISODate }
```

### 5.13 `result_schemas`  (dynamic AI return schema)
Teacher-defined JSON-Schema describing the shape the AI must return. Allows different schemas per subject/exam.
```json
{
  "_id": ObjectId,
  "name": "Standard Written Paper",
  "description": "Subjective paper with per-question marks + feedback",
  "schema_definition": {                     // JSON-Schema draft-07
    "type": "object",
    "required": ["student", "subject", "total_awarded", "total_max", "questions"],
    "properties": {
      "student":        { "type": "object",
                          "properties": {
                            "name": {"type":"string"}, "roll_no":{"type":"string"},
                            "class":{"type":"string"} } },
      "subject":        { "type": "string" },
      "exam_title":     { "type": "string" },
      "total_max":      { "type": "number" },
      "total_awarded":  { "type": "number" },
      "overall_feedback":{"type": "string"},
      "questions": {
        "type": "array",
        "items": {
          "type": "object",
          "required": ["q_no","awarded","max"],
          "properties": {
            "q_no":   {"type":"string"},
            "awarded":{"type":"number"},
            "max":    {"type":"number"},
            "feedback":{"type":"string"},
            "page_refs":{"type":"array","items":{"type":"integer"}},
            "confidence":{"type":"number"}
          }
        }
      }
    }
  },
  "created_by": ObjectId,
  "created_at": ISODate
}
```
Implementation re-uses the existing `schemas_collection` / schema UI pattern but adds a "Result schema" kind so it doesn't conflict with the current extraction schemas.

### 5.14 `batch_jobs`
```json
{
  "_id": ObjectId,
  "exam_id": ObjectId,
  "provider": "gemini" | "openai",
  "model": "gemini-2.0-flash" | "gemini-2.5-flash" | "gemini-2.5-pro" | "gpt-4.1-mini",
  "provider_batch_id": "batch_abc123" | null,
  "input_file_path": "storage/batches/{id}/input.jsonl",
  "uploaded_jsonl_path": "storage/batches/{id}/input_with_uris.jsonl" | null,
  "uploaded_gemini_files": ["files/xxx", "files/yyy"] | null,
  "output_file_path": "storage/batches/{id}/output.jsonl" | null,
  "item_count": 42,
  "completed_count": 0,
  "failed_count": 0,
  "status": "draft" | "review" | "submitted" | "in_progress"
          | "completed" | "failed" | "cancelled" | "expired",
  "submitted_at": ISODate | null,
  "completed_at": ISODate | null,
  "last_polled_at": ISODate | null,
  "poll_error": "string | null",
  "created_by": ObjectId,
  "created_at": ISODate
}
```

### 5.14 `batch_items` (UPDATED)
One per sheet inside a batch; ties sheet ↔ provider custom_id.
```json
{
  "_id": ObjectId,
  "batch_id": ObjectId,
  "sheet_id": ObjectId,
  "custom_id": "sheet_{sheet_id}",
  "prompt_preview": "string",
  "status": "pending" | "completed" | "failed",
  "error": "string | null",
  "raw_response": { ... } | null,
  "created_at": ISODate
}
```

### 5.16 `gradings`
```json
{
  "_id": ObjectId,
  "sheet_id": ObjectId,
  "exam_id": ObjectId,
  "batch_id": ObjectId,
  "result_schema_id": ObjectId,
  "result": { ...conforms to result_schema... },
  "total_awarded": 78, "total_max": 100,
  "status": "auto" | "reviewed" | "overridden" | "published",
  "reviewed_by": ObjectId | null,
  "reviewed_at": ISODate | null,
  "published_at": ISODate | null,
  "override_log": [ { "by":ObjectId,"at":ISODate,"patch":{...} } ],
  "created_at": ISODate
}
```

### 5.17 Model Answer Integration (NEW)

Model answers are integrated into the JSONL prompt through **three scenarios** depending on what the teacher provides:

| Scenario | How Teacher Provides | How It's Included in JSONL |
|----------|---------------------|---------------------------|
| **A. Typed per-question answers** | Teacher enters in "Model Answer" column during QP review | Text in prompt: `"Q1 (2 marks): ... Model answer: An object at rest stays at rest..."` |
| **B. Model answer document (PDF)** | Upload as separate document → AI extracts and links to questions | Extracted text stored in `question.expected_answer`, included as text in prompt |
| **C. Handwritten model answer sheets** | Upload as sample sheets (existing flow) | Images included in JSONL: `{"_file_ref": "storage/samples/..."}` |

#### Scenario A: Typed Per-Question Model Answers

During the **Review Questions** tab, the teacher sees an editable "Model Answer" column for each extracted question. The teacher types or pastes the model answer for each question.

```
┌────┬──────────────────────────────┬───────┬──────────────────────────────────┐
│ Q  │ Question                     │ Marks │ Model Answer                     │
├────┼──────────────────────────────┼───────┼──────────────────────────────────┤
│ Q1 │ What is Newton's first law?  │   2   │ [An object at rest stays at...] │
│ Q2 │ Define acceleration          │   1   │ [Rate of change of velocity]    │
│ Q7 │ Analyze circuit diagram      │   5   │ [Apply KVL: V = IR + IR...]     │
└────┴──────────────────────────────┴───────┴──────────────────────────────────┘
```

Data model:
```python
class QuestionItem(BaseModel):
    q_no: str
    question: str
    expected_answer: Optional[str] = None        # Teacher-entered or AI-extracted
    expected_answer_source: Optional[str] = None # "teacher_typed" | "ai_extracted"
    marks: int
```

#### Scenario B: Model Answer Document Upload

Teacher uploads a separate model answer PDF/document:

```
/exams/[id]/answer-key → Tab: "Model Answers"
Upload Model Answer Document (PDF/Text)
The AI will extract answers and link them to questions.
[Browse file] physics_answers.pdf
[Extract & Link to Questions]
```

Backend process:
1. Upload model answer PDF → rasterize to pages
2. AI analyzes: "Match each answer to the corresponding question number (Q1, Q2, etc.)"
3. Extracted answers stored in `question.expected_answer` per question with `expected_answer_source: "ai_extracted"`
4. Teacher reviews and edits in the question table

#### Scenario C: Handwritten Model Answer Sheets (Sample Sheets)

If the teacher has handwritten model answers (e.g., a "topper's answer sheet"), they upload as sample sheets. These are included as image references in the JSONL.

```
/exams/[id]/answer-key → Tab: "Sample Answers"
Upload Sample Answer Sheets
These serve as visual examples of good answers.
☑️ sample_01.pdf  - "Full marks example"
☑️ sample_02.png  - "Partial marks example"
```

## 6. Backend Implementation Plan

### 6.1 New dependencies (`backend/requirements.txt`)
`passlib[bcrypt]`, `python-jose[cryptography]`, `python-multipart`, `pymupdf`, `pillow`, `jsonschema`, `google-genai` (Gemini batch + extraction), `openai` (already indirectly via ai_service if using OpenAI batch).

### 6.2 Project layout
```
backend/
  core/       config.py, security.py, deps.py
  db/         database.py (adds all new collections)
  models/     auth.py, school.py, sheets.py, batches.py, gradings.py
  services/
    pdf_service.py              rasterize_pdf_to_pngs(file, out_dir, dpi=150)
    zip_service.py              extract & parse filename metadata
    question_extraction_service.py   NEW: extract questions from QP PDF
    jsonl_service.py            build_jsonl_line(sheet, key, qp_pages, samples, schema)
                                write_batch_input(batch_id, items)
                                parse_batch_output(output_file)
    batch_service.py            upload_files_for_batch(jsonl_path, batch_id) → (uri_jsonl_path, [file_names])
                                submit_batch, poll_batch, cancel_batch, ingest_results
                                (provider-agnostic adapter with Gemini + OpenAI impls)
    grading_service.py          validate_result_against_schema, apply_to_mongo
    ai_service.py               (existing; add helpers for sample/key prompt parts)
  routers/
    auth.py users.py classes.py subjects.py exams.py
    question_papers.py          NEW: upload, extract, status, pages review
    sheets.py batches.py gradings.py files.py
  workers/
    batch_poller.py             asyncio task polling submitted batches every N min
    extraction_worker.py        NEW: async extraction task runner
  main.py                       mounts routers + starts workers on startup event
```

### 6.3 Question Paper Extraction Service

**Model**: `gemini-2.0-flash` (cheap, fast, handles OCR + layout perfectly — ~$0.10/million tokens).

```python
# backend/services/question_extraction_service.py

async def extract_question_paper(exam_id: str, pdf_path: str) -> str:
    """
    Two-pass extraction:
    Pass 1: Rasterize PDF to page images (PyMuPDF @ 150 DPI)
    Pass 2: Per-page AI analysis (parallel) → consolidation
    Returns: extraction_task_id
    """
```

**Page analysis prompt (sent per page):**
```
Analyze this question paper page. Return JSON with:
1. questions_found: [{q_no, question_text, marks, has_diagram, has_graph, sub_parts}]
2. is_instruction_page: boolean
3. instruction_text: string (if instruction page)
4. marking_schemes: [{q_no, scheme_text}]
5. visual_elements: [{type: "diagram"|"graph"|"table"|"image", description}]
6. page_type: "instructions"|"questions"|"mixed"|"diagram_only"|"blank"
7. is_needed_for_grading: boolean (true if has questions, diagrams, or instructions)
```

**Consolidation prompt (single call after all pages analyzed):**
```
Consolidate these page analyses into a unified question list.
Total exam marks: {total_marks}
Handle: questions spanning multiple pages, duplicate detection, marking scheme aggregation.
Return: questions[], multi_page_questions[], marking_schemes[], total_marks_check, warnings[]
```

**Extraction states:**
```
pending → rasterizing → analyzing → consolidating → completed | failed
```

### 6.4 JSONL generation (File API approach — UPDATED with question paper pages)

For each mapped sheet, `jsonl_service.build_jsonl_line` produces one line using **file paths** (not base64). The prompt includes question paper pages that the teacher confirmed.

**Draft JSONL (local file paths):**
```json
{
  "key": "sheet_<sheet_id>",
  "request": {
    "contents": [
      { "role":"user", "parts":[
        {"text":"You are grading a handwritten answer sheet for {exam_title}. Complexity: {complexity_tier}."},
        {"text":"QUESTION PAPER REFERENCE:"},
        {"_file_ref": "storage/question_papers/{exam_id}/page_001.png"},
        {"_file_ref": "storage/question_papers/{exam_id}/page_006.png"},
        {"text":"ANSWER KEY:"},
        {"text":"Q1 (2 marks): What is Newton's first law?"},
        {"text":"Q11 (5 marks): Analyze the circuit diagram on page 6. Expected: V=IR, I=2.5A"},
        {"text":"Sample model sheet (guidance):"},
        {"_file_ref": "storage/samples/{exam_id}/sample_page_1.png"},
        {"text":"Student answer sheet pages:"},
        {"_file_ref": "storage/answer_sheets/{sheet_id}/page_001.png"},
        {"_file_ref": "storage/answer_sheets/{sheet_id}/page_002.png"},
        {"text":"Respond with JSON ONLY conforming to schema: <result_schema JSON>"}
      ] }
    ],
    "generationConfig": { "response_mime_type":"application/json",
                          "response_schema": "<result_schema>" }
  }
}
```

**Page inclusion logic:**
```python
def collect_pages_for_jsonl(answer_key: AnswerKey) -> List[str]:
    """Only include teacher-confirmed pages from question paper"""
    if not answer_key.included_page_refs:
        return []  # No QP uploaded or no pages confirmed
    
    pages = []
    for page_no in answer_key.included_page_refs:
        pages.append(f"storage/question_papers/{exam_id}/page_{page_no:03d}.png")
    return pages
```

**Step 2 — During submit, `batch_service.upload_files_for_batch()`:**
1. Read the draft JSONL, find all `_file_ref` entries
2. Upload each image to Gemini Files API via `client.files.upload()`
3. Replace `_file_ref` with `file_data` using the uploaded file URI
4. Write the final JSONL with URIs to `storage/batches/{id}/input_with_uris.jsonl`
5. Upload final JSONL to Gemini, create batch job

OpenAI Batch variant uses `custom_id` + `/v1/chat/completions` body with vision content parts.

- **Why File API**: The Gemini batch API has a **20 MB per-request inline limit**. The File API removes this constraint — each uploaded file can be up to 2 GB.
- **File expiry**: Gemini uploaded files expire after **48 hours**.
- **Model selection**: Single model per exam, based on `exam.complexity_tier`. No per-question routing.

### 6.5 Model Selection (Exam-Level, Not Per-Question)

```python
# backend/core/config.py

COMPLEXITY_MODEL_MAP = {
    "simple":   "gemini-2.0-flash",     # CBSE, basic recall, short answers
    "standard": "gemini-2.5-flash",     # State board, mixed questions
    "complex":  "gemini-2.5-pro",       # IIT-JEE/NEET, analytical, diagram-heavy
}

def get_model_for_exam(exam: Exam) -> str:
    return COMPLEXITY_MODEL_MAP.get(exam.complexity_tier, "gemini-2.5-flash")
```

Same model used for both question paper extraction (always `gemini-2.0-flash`) and grading (based on exam complexity tier).

### 6.6 Endpoints (new and updated)

Auth: `/auth/login`, `/auth/me`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`.

Users (admin/teacher): `GET/POST/PATCH/DELETE /users`, `POST /users/import` (CSV of students).

Classes, Subjects, Enrollments: standard CRUD with RBAC.

Exams:
- `POST /exams`, `PATCH /exams/{id}`, `GET /exams?class_id=...`.
- `POST /exams/{id}/answer-key` (JSON body — manual or hybrid mode).
- `POST /exams/{id}/sample-sheets` (multipart PDF/image/text with label).
- `POST /exams/{id}/result-schema` → link a `result_schemas` doc.

Question Papers (NEW):
- `POST /exams/{id}/question-paper/upload` → upload QP PDF, start extraction
- `GET /exams/{id}/question-paper/` → get QP with extracted questions and pages
- `GET /exams/{id}/question-paper/extraction-status` → poll extraction progress
- `POST /exams/{id}/question-paper/review` → teacher confirms pages, saves edits, saves attached images
- `POST /exams/{id}/question-paper/crop` → upload cropped image (multipart/base64), attach to question
- `DELETE /exams/{id}/question-paper/crop/{crop_id}` → remove attached image from question
- `POST /exams/{id}/question-paper/additional-pdf` → upload supplementary PDF (instructions/answer_key/reference)
- `GET /exams/{id}/question-paper/additional-pdfs` → list all additional PDFs for exam
- `DELETE /exams/{id}/question-paper/additional-pdf/{pdf_id}` → remove additional PDF
- `GET /files/question-papers/{exam_id}/pages/{n}` → serve QP page image
- `GET /files/question-papers/{exam_id}/crops/{crop_id}` → serve cropped attachment image

Answer sheets:
- `POST /exams/{id}/sheets/upload-zip` → background ZIP processing; returns `upload_batch_id`.
- `GET /exams/{id}/sheets`, `GET /sheets/{id}`.
- `PATCH /sheets/{id}` (student mapping edits).
- `DELETE /sheets/{id}/pages/{page_no}`, `POST /sheets/{id}/pages/reorder`.
- `POST /sheets/{id}/skip`.
- `GET /sheets/{id}/jsonl-preview` → returns the JSONL line that would be produced.

Batches:
- `POST /exams/{id}/batches` → builds JSONL over all `mapped` sheets; creates `batch_jobs` (status=`draft`) + one `batch_items` per sheet. Uses exam's complexity tier to select model.
- `GET /batches/{id}` → details + per-item list.
- `GET /batches/{id}/jsonl` → downloads the built JSONL.
- `POST /batches/{id}/submit` → uploads images to provider, creates provider batch.
- `POST /batches/{id}/cancel`, `POST /batches/{id}/refresh`.
- `GET /batches?exam_id=...` → listing with statuses.

Background poller (`workers/batch_poller.py`):
- Started in `main.py` via `@app.on_event("startup")`.
- Every 5 min (configurable) fetches every `batch_jobs` with status ∈ `{submitted, in_progress}`, calls provider `get(batch_id)`.
- On `completed` → downloads output file, parses it, validates against schema, upserts `gradings`.

Extraction worker (`workers/extraction_worker.py`):
- Started in `main.py` via `@app.on_event("startup")`.
- Listens for new extraction tasks in `extraction_tasks` collection.
- Runs extraction pipeline: rasterize → analyze pages → consolidate → save results.
- Updates `extraction_tasks` status in real-time for UI polling.

Gradings:
- `GET /gradings/{id}`, `PATCH /gradings/{id}`, `POST /gradings/{id}/publish`.
- `POST /exams/{id}/publish-all` → bulk publish.

Files: `/files/sheets/{id}/pages/{n}`, `/files/sheets/{id}/pdf`, `/files/question-papers/{exam_id}/pages/{n}`, `/files/exams/{id}/key-pdf`, `/files/exams/{id}/samples/{sid}`, `/files/batches/{id}/jsonl` — all auth-checked.

### 6.7 Reuse of existing code
- Existing `documents` + `schemas` (extraction) endpoints stay intact and are gated behind auth.
- `ai_service.extract_with_vision` reused for question paper page analysis.
- `pdf_service.rasterize_pdf_to_pngs` reused for QP rasterization.

## 7. Workflow End-to-End (what the teacher sees)

### Simple Paper Flow (manual entry)
1. **Setup**: create class → subjects → students → exam → select complexity tier → attach result schema.
2. **Answer key**: teacher enters questions manually OR uploads answer-key PDF.
3. **Upload ZIP** → backend rasterizes → sheets appear `pending_mapping`.
4. **Mapping** → sheet-by-sheet UI → `Save & Next` → sheets become `mapped`.
5. **Build batch** → JSONL assembled → review → submit to AI.
6. **Waiting** (24–48 h) → poller advances state.
7. **Result ingestion** → `gradings` with `status=auto`.
8. **Teacher review** → edit marks → `reviewed` / `overridden`.
9. **Publish** → students see results.

### Complex Paper Flow (AI extraction + Crop-to-Attach)
1. **Setup**: create class → subjects → students → exam → **select complexity tier** → attach result schema.
2. **Upload Question Paper PDF** → system rasterizes → AI extracts questions in background (30–90 seconds).
3. **Split-Screen Review**:
   - **Left panel**: PDF viewer of uploaded question paper (with tab support for additional PDFs). Teacher selects a region (crop) to attach to a question.
   - **Right panel**: Expandable list of extracted questions. Click a question to make it "active" and expand its edit form.
   - **Crop-to-attach workflow**: Crop a diagram/image region from PDF → popup shows cropped preview → confirm → image attached to active question.
   - **Multi-PDF support**: Upload additional PDFs (instructions, model answers, reference docs) as separate tabs. Crop from any PDF and attach to any question.
4. **Save review**: Confirm pages, save question edits + attached images → `question_papers` + `answer_keys` persisted.
5. **Upload ZIP** → backend rasterizes → sheets appear `pending_mapping`.
6. **Mapping** → sheet-by-sheet UI → `Save & Next` → sheets become `mapped`.
7. **Build batch** → JSONL assembled with confirmed QP pages + attached cropped images → review → submit to AI (model selected by exam complexity tier).
8. **Waiting** (24–48 h) → poller advances state.
9. **Result ingestion** → `gradings` with `status=auto`.
10. **Teacher review** → edit marks → `reviewed` / `overridden`.
11. **Publish** → students see results.

## 8. Frontend Implementation Plan (Next.js 16 App Router)

> Before coding, read `node_modules/next/dist/docs/` (per `frontend/AGENTS.md`) for Next.js 16 conventions; do not assume older App Router patterns.

### 8.1 Auth & layout
- `src/lib/api.ts` (auth-injecting fetch), `src/lib/auth.tsx` (context), `src/middleware.ts` (role guard).
- Pages: `/login`, `/forgot-password`, `/reset-password?token=...`, `/change-password`. No `/register` (admin-only user creation inside `/users`).
- Role-aware header in `layout.tsx`.

### 8.2 Admin/teacher surfaces
- `/users` — list/create/import (CSV) students, create teachers (admin only).
- `/classes`, `/classes/[id]`, `/subjects`.
- `/exams`, `/exams/[id]` with tabs: **Answer Key** | **Samples** | **Result Schema** | **Sheets** | **Batches** | **Results**.

### 8.3 Exam Creation / Edit
- Complexity tier selector dropdown on exam create/edit form:
  - Simple (CBSE-style, text-based answers)
  - Standard (Mixed questions, some diagrams)
  - Complex (IIT-JEE/NEET, heavy diagrams, multi-step reasoning)
- Selection affects model used for both extraction and grading.

### 8.4 Answer Key Page `/exams/[id]/answer-key` (REVISED)

**Tab 1: "Upload Question Paper"** (for complex papers)
- Drag-drop multi-page PDF upload
- After upload, shows extraction progress:
  ```
  Step 1: ✅ Converting PDF to images (25 pages)
  Step 2: 🔄 Analyzing pages with AI (18/25)
          Processing page 19...
          ████████████████████░░░░ 72%
  Step 3: ⏳ Consolidating results
  ```
- Polls `GET /exams/{id}/question-paper/extraction-status` every 2 seconds
- On completion, auto-redirects to Tab 2

**Tab 2: "Review Questions" — Split-Screen with Crop-to-Attach** (appears after extraction)
- **Split-screen layout**:
  - **Left panel (60% width)**: Full PDF viewer of uploaded question paper
    - Renders pages via pdf.js on a canvas
    - Supports pan, zoom, and region selection (click-drag crop)
    - Tab bar at top to switch between: primary QP PDF + any additional uploaded PDFs
    - When a region is cropped, a floating popup appears showing the cropped thumbnail with two buttons:
      - **"Attach to Q{q_no}"** (active question) — sends crop data to backend, saves image, attaches to question
      - **"Dismiss"** — cancels the crop
  - **Right panel (40% width)**: Scrollable list of extracted questions
    - Each question is a collapsible card showing: Q.No, question text, marks, has_diagram indicator
    - Click a question card → it becomes "active" (highlighted border), expands to show full edit form:
      - Editable fields: question text, marks, keywords, expected answer, marking scheme
      - **Attached images section**: thumbnails of all cropped images attached to this question, with [Remove] button
      - [Save] button per question
    - "Active question" state: only one question is active at a time; the crop popup targets this question
    - If no question is active when a crop is made, popup shows "Select a question first"
- **Multi-PDF tab bar** (above the PDF viewer):
  - Primary tab: "Question Paper (original.pdf)" — always present
  - Additional tabs: uploaded via [+ Add PDF] button → modal to upload + label PDF (type: instructions / answer_key / reference)
  - Clicking a tab switches which PDF is rendered in the canvas
  - Crops from any PDF can be attached to any question
- **Workflow**: Teacher uploads PDF → extraction completes → reviews questions in split-screen → crops diagrams/images → attaches to correct questions → edits question text → saves

**Tab 3: "Pages for Grading"** (appears after extraction)
- Checklist of all QP pages with AI-suggested inclusions pre-checked:
  ```
  ☑️ Pg 1  Instructions      "General guidelines"
  ☑️ Pg 2  Q1, Q2, Q3        "Short answers"
  ☐  Pg 4  Blank             "Separator page"
  ☑️ Pg 5  Q7 + Diagram      "Circuit diagram for Q7"
  ```
- Bulk actions: [Select All] [Deselect Unused]
- Shows estimated token count and cost impact
- "Confirm Pages" button saves `included_page_refs`

**Tab 4: "Sample Answers"** (existing)
- Upload model answer sheets if available
- Optional: "No model answers available" checkbox

**Tab 5: "Manual Entry"** (for simple papers without QP upload)
- Add questions one-by-one
- Shown when no question paper has been uploaded

### 8.5 ZIP upload wizard `/exams/[id]/upload`
Same 3-step flow as the demo (Upload → Mapping one-by-one → Done) but talking to the backend:
- Upload card → `POST /exams/{id}/sheets/upload-zip`. Poll `upload_batches`.
- Mapping step: `Process PDF N/M`, pre-filled inputs, page thumbnails, zoom modal, delete page, **Skip** / **Save & Next**.
- Bottom "Saved Records" list matches demo (expand/edit/delete).

### 8.6 Batch management `/exams/[id]/batches`
- "Prepare JSONL" button → `POST /exams/{id}/batches`.
- Draft view: item count, model display (auto-selected from exam complexity tier), **Download JSONL**, **Remove item**, **Submit to AI**.
- Model info display: "Using gemini-2.5-flash (Standard complexity) — Est. $0.25/student"
- Submit flow: multi-step progress → "Submitted"
- Submitted view: badge with status, `completed_count / item_count` progress, `last_polled_at`, manual **Refresh** button, **Cancel**.

### 8.7 Grading review `/sheets/[id]`
- Left: page image carousel with zoom.
- Right: dynamic form from `result_schema` — for each question: `awarded`, `max`, `feedback`, editable.
- Buttons: **Mark Reviewed**, **Publish**, **Back to Exam**. Audit log panel shows `override_log`.

### 8.8 Student view `/students/me`
- Table of exams with `status=published` gradings only. Row expands to show per-question breakdown + total. Read-only.

### 8.9 Password flows
- `/forgot-password` → enter email → `POST /auth/forgot-password` → UI shows token message.
- `/reset-password?token=...` → new password form → `POST /auth/reset-password`.

## 9. Dynamic schema handling

- `result_schemas` stores **JSON-Schema draft-07** documents; teachers can create many and assign per exam.
- Backend validates every AI-returned payload against the exam's linked schema using `jsonschema.validate`. On failure: `batch_items.status=failed` with `error`.
- Frontend renders review forms by walking the schema (simple field-by-field renderer for objects, arrays of objects for `questions`).
- Totals (`total_awarded`, `total_max`) are read from the payload if present; else computed by summing `questions[*].awarded` / `questions[*].max`.

## 10. Provider abstraction (Batch API)

`services/batch_service.py` exposes:
```
upload_files_for_batch(input_jsonl_path, batch_id) -> (uri_jsonl_path, [uploaded_file_names])
submit(provider, model, uri_jsonl_path) -> provider_batch_id
status(provider, provider_batch_id) -> {status, completed, failed, output_file_url?}
download_output(provider, provider_batch_id, dest_path)
cancel(provider, provider_batch_id)
cleanup_expired_files(file_names)
```
Implementations:
- **Gemini Batch**: via `google-genai` `files.upload()`, `batches.create`, `batches.get`.
- **OpenAI Batch**: `/v1/files` + `/v1/batches`.
Model is determined by exam's `complexity_tier` — not selectable per batch.

**Gemini File API limits**:
- Per-request inline limit: 20 MB (bypassed by using File API URIs)
- Per-file upload limit: 2 GB
- Max requests per batch: 200,000
- File expiry: 48 hours after upload

## 11. Integration / migration notes

- Existing extraction flow (`documents`, `schemas`) remains; gated behind auth.
- `main.py` is split into routers incrementally; no breaking change to current endpoints' paths.
- `.env` additions: `JWT_SECRET`, `JWT_EXPIRE_MIN=1440`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`, `BATCH_PROVIDER_DEFAULT=gemini`, `BATCH_POLL_INTERVAL_SEC=300`, `GEMINI_EXTRACTION_MODEL=gemini-2.0-flash`, `GEMINI_SIMPLE_MODEL=gemini-2.0-flash`, `GEMINI_STANDARD_MODEL=gemini-2.5-flash`, `GEMINI_COMPLEX_MODEL=gemini-2.5-pro`.
- No email sender is configured; password reset tokens are visible to admins for handoff.

## 12. Suggested build order

1. **Auth core + password reset** (backend + `/login`, `/forgot`, `/reset`, middleware, role-aware header).
2. **Users / Classes / Subjects / Students** CRUD + import.
3. **Exams + complexity tier + Answer keys + Sample sheets + Result schemas** (backend + UI).
4. **Question Paper Upload + AI Extraction + Split-Screen Review with Crop-to-Attach** (new: `question_papers` collection, extraction service, progress polling, split-screen review UI with PDF cropping and image attachment).
5. **ZIP ingestion pipeline** (`pdf_service`, `zip_service`, upload batch progress, file server).
6. **Mapping UI** (replicate demo flow on top of backend).
7. **JSONL builder + draft batch** (`jsonl_service`, updated to include QP pages + attached cropped images).
8. **Batch submission + File API uploads + provider adapters + poller** (Gemini first, OpenAI second).
9. **Grading ingestion + dynamic schema validator + review UI + override log**.
10. **Publish workflow + Student portal** (`/students/me`).
11. **Polish**: skeletons, error boundaries, notification badges for batch completion, bulk actions.

## 13. Locked decisions (from clarifications)

- User creation: **admin or teacher only**; no public self-registration.
- Password reset: **yes**, in-app token flow (no email verification, no email sending).
- Marks visibility: **only after teacher review & publish**.
- Grading path: **only Batch API**; JSONL is the canonical artifact and is reviewable before submission.
- Sample answer sheets: supported as PDF / image / text. Uploaded to Gemini Files API during batch submit.
- Return schema: dynamic per-exam JSON-Schema, validated server-side; UI renders generically.
- Supports multiple subjects / students / exams concurrently; batches are scoped per exam but many exams may have batches in flight in parallel.
- **Question paper extraction**: Uses `gemini-2.0-flash` (cheap, fast, OCR+layout capable).
- **Model selection**: Set once per exam via `complexity_tier` (simple/standard/complex). Same model used for extraction (fixed to `gemini-2.0-flash`) and grading (tier-based). No per-question routing.
- **Page inclusion**: AI auto-suggests pages during extraction; teacher confirms final set via UI checklist before batch submission.
- **Diagrams/graphs in prompts**: Cropped image attachments are preferred over full page images. Teacher actively crops and attaches the relevant diagram region to the question during the split-screen review. If no crop is attached, the full page image is included as fallback.

## 14. Implementation Difficulties & Conflicts

### 14.1 Styling Conflicts
| Issue | Description | Resolution |
|-------|-------------|-------------|
| **CSS Variable Mismatch** | `globals.css` uses `--bg-primary: #0a0a0f` while `workflow_diagram.html` uses `--bg: #0f1117`. | Replace `globals.css` variables entirely with workflow_diagram.html values. |
| **Component Class Differences** | Existing code uses `.glass-panel`, `.btn-primary` with different styling. | Create new component classes; migrate gradually. |
| **Font Differences** | `globals.css` uses `'Outfit'` font; workflow_diagram.html uses `'Segoe UI'`. | Switch to Segoe UI. |

### 14.2 Backend Challenges
| Issue | Description | Impact | Mitigation |
|-------|-------------|---------|------------|
| **No Existing Auth System** | Current `main.py` has zero authentication. | High — blocks all other features | Auth first (Phase 1). |
| **MongoDB Collection Migration** | Currently only `documents` and `schemas` collections exist. Need 13+ new collections. | Medium — need schema models + indexes | Create all `models/` files before routers. |
| **Async Extraction Worker** | Need background worker for multi-step AI extraction with real-time progress. | Medium — concurrent task management | Use `extraction_tasks` collection + asyncio worker; poll via REST. |
| **Batch API Provider Differences** | Gemini and OpenAI Batch APIs have different formats. | High — need abstraction layer | Build `batch_service.py` with provider adapter pattern. |
| **Background Polling** | Asyncio worker polls every 5 min for batch status. | Medium — FastAPI startup events | `@app.on_event("startup")` to launch. |
| **Large JSONL File Handling** | Batch input/output files can be large. | Medium — memory/performance | Stream read/write; use file paths in draft, File API during submit. |
| **Gemini File API Upload Pipeline** | 20 MB per-request inline limit requires File API uploads. | High — adds upload step; track files for expiry | Upload during submit with progress; store file names for cleanup. |
| **Dynamic JSON-Schema Validation** | Validating AI responses against teacher-defined schemas. | Medium — jsonschema complexity | `jsonschema.validate()` with draft-07; log errors to `batch_items.error`. |

### 14.3 Frontend Challenges
| Issue | Description | Impact | Mitigation |
|-------|-------------|---------|------------|
| **Next.js 16 Breaking Changes** | AGENTS.md warns: "This is NOT the Next.js you know". | High — wrong patterns will break | Read `node_modules/next/dist/docs/` before coding. |
| **Dynamic Form Generation** | Result schema varies per exam; need generic form renderer. | High — complex UI logic | Walk JSON-Schema recursively. |
| **Extraction Progress UX** | AI extraction takes 30-90 seconds; UI must show granular progress. | Medium — requires polling | Poll every 2s; show step-by-step progress with page counter. |
| **Split-Screen PDF Viewer** | pdf.js canvas rendering + region selection crop + popup confirmation + active question state management. | High — complex canvas interaction | Use pdf.js for rendering; canvas overlay for crop selection; React state for active question. |
| **Crop-to-Attach State Machine** | Crop → preview popup → attach/dismiss → save to backend → update question card. | High — multi-step async flow | Track crop state (none/selecting/previewing/attaching); debounce crop changes. |
| **Multi-PDF Tab Switching** | Upload additional PDFs, render on same canvas, maintain crop coordinates across PDFs. | Medium — PDF state management | Store per-PDF render state; clear crop on tab switch. |
| **QP Page Review UI** | Two-column layout: page viewer + question table; click-to-highlight. | Medium — complex layout | Use CSS grid; sync scroll state between columns. |
| **Page Inclusion Checklist** | Pre-checked list of pages; bulk select/deselect; token estimate. | Low — straightforward UI | Checkbox list with computed stats. |
| **Role-Aware Middleware** | Pages must be guarded by JWT role checks. | Medium | `middleware.ts` checks JWT; redirects based on role. |
| **Mapping UI State Management** | Sheet mapping requires: current PDF state, page deletions, form edits. | High — complex state | Use React state + context; `useReducer` for complex state. |
| **Concurrent Batch Monitoring** | Multiple exam batches can run simultaneously. | Low | Dashboard fetches all `batch_jobs` with active statuses. |

### 14.4 Integration Conflicts
| Issue | Description | Resolution |
|-------|-------------|------------|
| **Existing Endpoint Paths** | Current `/documents`, `/schemas` endpoints use different auth model. | Gate behind new auth. Keep paths unchanged. |
| **CORS Configuration** | Currently `allow_origins=["*"]`. | Update `main.py` CORS to specific frontend URL from `.env`. |
| **Storage Directory Structure** | Plan requires new `question_papers/` directory + `crops/` subdirectory + `additional/` subdirectory. | Create on startup; add to `.gitignore`. |
| **Environment Variables** | Many new `.env` vars needed. | Document all in `.env.example`; use `core/config.py` with defaults. |
| **Gemini File Expiry (48 hours)** | Files expire after 48 hours. | Monitor batch completion; track `uploaded_gemini_files`; re-upload if needed. |
| **Crop Images vs Full Page Images in JSONL** | Original plan included full QP page images. New plan uses cropped images. Both must coexist: cropped images for questions with diagrams, full pages as fallback/context. | JSONL includes cropped images first, then any un-cropped full pages for questions without attachments. |
| **pdf.js vs PyMuPDF** | Frontend uses pdf.js for rendering; backend uses PyMuPDF for rasterization. Both produce PNGs but at different scales. | Store crop bbox in PDF coordinate space (not pixel space); backend converts to pixel coords at render time. |

### 14.5 Critical Path Dependencies
```
Auth System (1) → Users/Classes/Subjects (2) → Exams + Keys + Complexity (3)
                                                 ↓
                                    Question Paper Extraction (4)
                                                 ↓
                                     ZIP Ingestion (5) → Mapping UI (6)
                                                 ↓
                                     JSONL Builder (7) → Batch Submit (8)
                                                 ↓
                                     Grading Ingestion (9) → Review (10) → Publish (11)
```
**Blockers if skipped**: Cannot test end-to-end without Auth (Phase 1). Cannot upload sheets without Classes/Exams (Phase 2-3). Cannot build JSONL without confirmed pages from QP extraction (Phase 4).

### 14.6 Estimated Complexity Ratings
| Phase | Feature | Complexity (1-5) | Reason |
|-------|---------|------------------|--------|
| 1 | Auth core + password reset | ★★★☆☆ | Well-documented patterns; new to codebase |
| 2 | Users/Classes/Subjects CRUD | ★★☆☆☆ | Standard CRUD with RBAC |
| 3 | Exams + Complexity + Keys + Schemas | ★★★☆☆ | PDF extraction reuse; sample sheet upload |
| 4 | Question Paper Upload + AI Extraction + Split-Screen Review + Crop-to-Attach | ★★★★★ | Async two-pass extraction; progress polling; pdf.js viewer; canvas cropping; multi-PDF tabs; image attachment pipeline |
| 5 | ZIP ingestion pipeline | ★★★★☆ | PyMuPDF integration; background processing |
| 6 | Mapping UI | ★★★★☆ | Complex state; image handling; replicate demo |
| 7 | JSONL builder + QP page + crop inclusion | ★★★★☆ | File I/O; page reference logic; attached image inclusion |
| 8 | Batch submit + File API + poller | ★★★★★ | Provider abstraction; File API upload; async polling; crop image upload |
| 9 | Grading ingestion + review UI | ★★★★☆ | Dynamic schema; form generation; override log |
| 10 | Publish + Student portal | ★★★☆☆ | Read-only views; RBAC checks |
| 11 | Polish | ★★☆☆☆ | UI/UX improvements; non-blocking |

## 15. Split-Screen Review with Crop-to-Attach — Detailed Specification

### 15.1 Purpose

This feature replaces the static question review UI with an interactive split-screen workflow. Instead of auto-linking questions to full QP pages, the teacher actively crops diagram/image regions from the PDF and attaches them to specific questions. This produces cleaner, more targeted JSONL prompts with only the relevant visual context per question, skipping the need for a separate answer key addition step.

### 15.2 UI Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [Question Paper (original.pdf)]  [+ Instructions.pdf]  [+ Answer Key.pdf] │  ← PDF Tab Bar
├──────────────────────────────┬──────────────────────────────────────────────┤
│                              │  Extracted Questions                         │
│  ┌────────────────────────┐ │  ┌──────────────────────────────────────────┐ │
│  │                        │ │  │ ▼ Q1  What is Newton's first law?  [2M]  │ │
│  │   PDF Viewer Canvas    │ │  │   [question_text: editable]               │ │
│  │   (pdf.js rendered)    │ │  │   [marks: 2] [keywords: force, motion]   │ │
│  │                        │ │  │   Attached images: (none)                 │ │
│  │   ▲ Click-drag to      │ │  │   [Save]                                  │ │
│  │     select region      │ │  └──────────────────────────────────────────┘ │
│  │                        │ │  ┌──────────────────────────────────────────┐ │
│  │                        │ │  │ ▶ Q7  Analyze the circuit diagram  [5M]  │ │ ← ACTIVE (highlighted)
│  │                        │ │  │ ┌──────────────────────────────────────┐ │ │
│  └────────────────────────┘ │ │ │ [question_text: editable]              │ │ │
│                              │ │ │ [marks: 5] [keywords: circuit, V=IR] │ │ │
│                              │ │ │ Attached images:                      │ │ │
│                              │ │ │ ┌─────┐ ┌─────┐                      │ │ │
│                              │ │ │ │img1 │ │img2 │ [×]                  │ │ │
│                              │ │ │ └─────┘ └─────┘                      │ │ │
│                              │ │ │ [Save]                                │ │ │
│                              │ │ └──────────────────────────────────────┘ │ │
│                              │ └──────────────────────────────────────────┘ │
│                              │  [+] Add Question                            │
│                              │                                              │
│                              │  [Confirm Pages →]  [Save & Continue →]     │
└──────────────────────────────┴──────────────────────────────────────────────┘
```

**Crop Popup** (appears when a region is selected on the canvas):
```
┌─────────────────────────────────┐
│  [Cropped Image Preview]        │
│                                 │
│  Attach to: Q7 (active)         │
│  Label: [diagram] [________]    │
│                                 │
│  [✓ Attach to Q7]  [✕ Dismiss] │
└─────────────────────────────────┘
```

If no question is active when a crop is made:
```
┌─────────────────────────────────┐
│  [Cropped Image Preview]        │
│                                 │
│  ⚠ No question selected.        │
│  Click a question on the right  │
│  to make it active, then crop.  │
│                                 │
│  [✕ Dismiss]                    │
└─────────────────────────────────┘
```

### 15.3 Data Flow

1. **Upload**: Teacher uploads QP PDF → extraction runs → questions appear in right panel
2. **Activate**: Teacher clicks a question card → it becomes "active" (highlighted border, expanded form)
3. **Crop**: Teacher click-drags a region on the PDF canvas → rectangle overlay shows selection
4. **Preview**: On mouse-up, the selected region is extracted from the canvas as a PNG data URL → popup shows preview
5. **Attach**: Teacher clicks "Attach to Q{n}" → frontend sends crop data (base64 image, bbox, page_no, source_pdf, label) to `POST /exams/{id}/question-paper/crop`
6. **Backend**: `crop_service.save_crop()` extracts the region, saves as PNG in `storage/question_papers/{exam_id}/crops/`, creates `question_paper_crops` document
7. **Update**: Frontend receives crop_id → adds thumbnail to the active question's "Attached images" section
8. **Save**: Teacher clicks [Save] on question → `POST /exams/{id}/question-paper/review` persists question edits + crop references
9. **JSONL**: During batch build (Phase 7), each question's attached images are included as `_file_ref` entries in the JSONL line

### 15.4 Crop BCoordinate System

- Crops are stored as **PDF coordinate space** bbox: `{ x, y, width, height }` in points (72 DPI)
- Frontend captures crop in **canvas pixel space** → converts to PDF coordinates using: `pdf_coord = canvas_coord / (dpi / 72)`
- Backend re-rasters the region at the desired output DPI using PyMuPDF: `pix = page.get_pixmap(clip=bbox, dpi=150)`
- This ensures crops remain accurate regardless of zoom level or canvas scale

### 15.5 Storage Layout

```
storage/
  question_papers/
    {exam_id}/
      original.pdf                    # Primary QP PDF
      page_001.png ... page_025.png   # Rasterized pages (150 DPI)
      crops/
        q7_diagram_001.png            # Cropped attachment for Q7
        q7_graph_002.png              # Second crop for Q7
        q11_circuit_001.png           # Cropped attachment for Q11
      additional/
        instructions.pdf              # Supplementary PDF
        answer_key.pdf                # Supplementary PDF
```

### 15.6 JSONL Integration (Phase 7)

For each question with attached crops:
```json
{"text": "Q7 (5 marks): Analyze the circuit diagram below."},
{"_file_ref": "storage/question_papers/exam_001/crops/q7_diagram_001.png"},
{"_file_ref": "storage/question_papers/exam_001/crops/q7_graph_002.png"},
```

For questions without crops (fallback):
```json
{"text": "Q1 (2 marks): What is Newton's first law?"},
{"text": "Refer to question paper page 2 for context."},
{"_file_ref": "storage/question_papers/exam_001/page_002.png"},
```

### 15.7 Conflicts with Subsequent Steps

| Step | Conflict | Resolution |
|------|----------|------------|
| **Phase 7 (JSONL Builder)** | Must include both crop images and full page references. | Priority: crops first, full pages as fallback for questions without crops. |
| **Phase 8 (Batch Submit)** | Crop images must be uploaded to Gemini Files API alongside student pages and QP pages. | `batch_service.upload_files_for_batch()` scans all `_file_ref` entries including crop paths; deduplicates and uploads. |
| **Phase 9 (Grading Review)** | AI response may reference crop images by position in prompt. | Prompt text explicitly labels each image: "Diagram for Q7:" before the crop reference. |
| **Existing `diagram_page_refs`** | Old schema used page references; new schema uses crop attachments. | Both coexist: `diagram_page_refs` for backward compatibility, `attached_images` for new crops. |
| **Token budget** | Each crop image adds tokens to the prompt. | Teacher controls what gets attached; no auto-inclusion of full pages when crops exist. |
