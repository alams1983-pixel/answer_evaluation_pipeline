# Evaluation Pipeline - System Architecture & Comprehensive Overview

## 📌 Project Summary
The **Evaluation Pipeline** is an end-to-end **AI-Driven Answer Sheet Evaluation & Institute Management System**. It digitizes, processes, and evaluates handwritten or printed student answer sheets using Vision LLMs (Gemini / OpenAI).

```
   ┌───────────────────────┐
   │ School Admin / Teacher│
   └───────────┬───────────┘
               │
               ▼
┌──────────────────────────────┐       ┌──────────────────────────────┐
│  Exam & Question Paper Setup │ ─────►│ AI Question & Rubric Parsing │
└──────────────────────────────┘       └──────────────────────────────┘
               │                                      │
               ▼                                      ▼
┌──────────────────────────────┐       ┌──────────────────────────────┐
│  Answer Sheet PDF/ZIP Upload │ ─────►│ Auto-Matching Roll No / Name │
└──────────────────────────────┘       └──────────────────────────────┘
                                                      │
                                                      ▼
                                       ┌──────────────────────────────┐
                                       │ Async LLM Batch Evaluation   │
                                       │ (Gemini 2.5 / OpenAI GPT-4o) │
                                       └──────────────┬───────────────┘
                                                      │
                                                      ▼
   ┌───────────────────────┐           ┌──────────────────────────────┐
   │ Student Results Portal│ ◄─────────│ Split-Screen Manual Review   │
   └───────────────────────┘           └──────────────────────────────┘
```

---

## 🛠️ Technology Stack

### **Backend (`/backend`)**
* **Framework:** Python / FastAPI
* **Database:** MySQL (SQLAlchemy 2.0 AsyncSession with `asyncmy` driver and UUID primary keys)
* **AI & Vision Services:** `google-genai` (Gemini 2.5 Flash/Pro), OpenAI API (Batch API support)
* **Document Processing:** PyMuPDF (`fitz`), Pillow (PIL)
* **Auth & Security:** JWT authentication (`PyJWT`), Passlib bcrypt hashing, Role-Based Access Control (`admin`, `teacher`, `student`)

### **Frontend (`/frontend`)**
* **Framework:** Next.js (App Router, React 19, TypeScript)
* **Styling:** Custom glassmorphism & dark mode visual hierarchy (`globals.css`)
* **State & Auth:** React Context (`AuthContext`, `LayoutContext`), Custom API client with Bearer JWT auto-injection (`lib/api.ts`)
* **Interactive Canvas Tools:** HTML5 Canvas PDF page renderer (`PDFViewerCanvas`), Bounding-box diagram cropper (`CropOverlay`), Side-by-side evaluation reviewer (`SplitScreenReview`)

---

## 📂 Codebase Directory Architecture

### **1. Backend Structure (`/backend`)**
```
backend/
├── main.py                  # FastAPI entry point, CORS, startup index creation, worker launch
├── core/
│   ├── config.py            # Pydantic BaseSettings (DB URL, JWT Secret, Model defaults)
│   ├── deps.py              # JWT authentication & Role-Based Access Control (RBAC) guards
│   └── security.py          # Password hashing (bcrypt) & JWT token handling
├── db/
│   └── database.py          # Motor async MongoDB collections initialization
├── models/                  # Pydantic schemas (auth, school, sheets, gradings, batches)
├── routers/                 # FastAPI REST API endpoints
│   ├── auth.py              # Login, token refresh, password resets
│   ├── users.py & students.py# User management & CSV student bulk import
│   ├── classes.py & subjects.py # Class and subject management
│   ├── exams.py             # Exam creation, status lifecycle, student enrollment sync
│   ├── question_papers.py   # Question paper uploads, AI extraction, diagram region crops
│   ├── sheets.py            # PDF/ZIP upload, page splitting, manual & auto mapping
│   ├── batches.py           # Batch job creation, submission, status polling, JSONL export
│   ├── gradings.py          # Saving, updating, overriding, and publishing student grades
│   ├── files.py             # Image file streaming endpoint for page images & crops
│   └── dashboard.py         # Role-specific analytics dashboard
├── services/                # Business logic & AI pipelines
│   ├── question_extraction_service.py # Parallel vision analysis with Gemini to extract questions/rubrics
│   ├── auto_match_service.py          # Weighted match algorithm (Roll No + Name match)
│   ├── batch_service.py               # Provider abstraction for Gemini / OpenAI batch APIs
│   ├── grading_service.py             # Schema validation and score upserts
│   ├── pdf_service.py & crop_service.py # PDF page rasterization & bounding-box cropping
│   └── jsonl_service.py & zip_service.py# Batch payload generation & ZIP extraction
└── workers/                 # Async background processes
    ├── batch_poller.py      # Background loop polling active LLM batch jobs
    └── extraction_worker.py # Background monitor for question paper extractions
```

### **2. Frontend Structure (`/frontend`)**
```
frontend/src/
├── app/                     # Next.js App Router Pages
│   ├── page.tsx             # Role-aware main dashboard (Stats & navigation)
│   ├── login/               # Authentication page
│   ├── users/               # Admin user management
│   ├── students/            # Student roster management with CSV Bulk Import
│   ├── classes/ & subjects/ # Class & subject allocation pages
│   ├── result-schemas/      # Dynamic JSON grading schema builder
│   ├── exams/               # Exam dashboard & creation
│   └── exams/[id]/          # Exam detail workspace
│       ├── upload/          # Batch answer sheet uploader (ZIP/PDF)
│       ├── batches/         # LLM Batch job management dashboard
│       └── assign-results/  # Answer sheet mapping & auto-matching view
├── components/              # Reusable UI components
│   ├── SplitScreenReview.tsx # Side-by-side evaluation & manual score correction UI
│   ├── QuestionPaperTab.tsx  # Extracted questions preview & visual editor
│   ├── CropOverlay.tsx       # Interactive bounding-box region cropper
│   ├── SchemaBuilder.tsx     # Dynamic grading result schema designer
│   ├── ZipUpload.tsx         # Drag-and-drop ZIP file uploader with progress tracking
│   └── StudentLookupDropdown.tsx # Autocomplete student mapping input
└── lib/
    ├── api.ts               # Centralized fetch wrapper & TypeScript API models
    ├── auth.tsx              # Auth Context Provider & token management
    └── schema-builder.ts    # Grading schema structures & validation helpers
```

---

## 🔄 Core Workflows

### **1. Exam & Academic Roster Setup**
1. Admin creates Classes and Subjects, assigns Teachers, and imports Students via CSV.
2. Teachers create an Exam assigned to a Class and Subject, linking a dynamic Result Schema.
3. Student roster is automatically linked to the exam (`exam_students` collection).

### **2. Question Paper AI Extraction & Answer Key Generation**
1. Teacher uploads a Question Paper PDF.
2. `question_extraction_service.py` converts PDF pages into 150 DPI PNG images.
3. Gemini Vision API analyzes pages in parallel to parse:
   - Question numbers, full text, marks, sub-parts, and keywords.
   - Marking scheme / rubric criteria.
   - Visual elements (diagrams, graphs, instruction pages).
4. Consolidated results form the **Answer Key**.
5. Teachers can select diagram regions on the PDF using `CropOverlay.tsx` and attach cropped images to specific questions.

### **3. Answer Sheet Ingestion & Roll No Auto-Matching**
1. Teachers upload scanned Answer Sheets as multi-page PDFs or ZIP archives.
2. `pdf_service.py` splits answer sheets into individual high-res page images.
3. `auto_match_service.py` executes a multi-criteria scoring algorithm comparing extracted sheet info against enrolled students:
   - **Roll No Exact Match (60% weight)**
   - **Name Overlap (40% weight)**
4. Auto-matched suggestions are displayed on the frontend for one-click approval.

### **4. Async LLM Batch Evaluation Pipeline**
1. Teacher initiates an **LLM Batch Job** (Gemini 2.5 Flash / OpenAI GPT-4o mini).
2. `jsonl_service.py` constructs batch JSONL files containing student page images + question paper key + rubric requirements.
3. Requests are dispatched to the LLM Provider's Batch API.
4. `batch_poller.py` polls job status in the background.
5. On completion, results are downloaded, schema-validated, and saved to `gradings_collection`.

### **5. Human Review & Result Publishing**
1. Teacher opens `SplitScreenReview.tsx`:
   - Left side: High-res student answer sheet PDF canvas.
   - Right side: AI marks awarded, breakdown, and feedback.
2. Teachers can edit marks or override feedback, which logs an `override_log`.
3. Teacher clicks **Publish All** to make verified marks visible on Student accounts.
