import os
import json
import asyncio
import time
import bson
import concurrent.futures
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types

from core.config import settings, COMPLEXITY_EXTRACTION_MODEL
from services.pdf_service import rasterize_pdf_to_pngs
from db.database import (
    question_papers_collection,
    extraction_tasks_collection,
    answer_keys_collection,
    exams_collection,
)


PAGE_ANALYSIS_PROMPT = """Analyze this question paper page. Return ONLY valid JSON (no markdown, no code blocks) with this exact structure:

{
  "questions_found": [
    {
      "q_no": "1",
      "question_text": "full question text as written",
      "marks": 5,
      "has_diagram": false,
      "has_graph": false,
      "sub_parts": ["(a)", "(b)"]
    }
  ],
  "is_instruction_page": false,
  "instruction_text": "",
  "marking_schemes": [
    {
      "q_no": "1",
      "scheme_text": "marking scheme if mentioned"
    }
  ],
  "visual_elements": [
    {
      "type": "diagram",
      "description": "brief description",
      "related_question": "1"
    }
  ],
  "page_type": "questions",
  "is_needed_for_grading": true
}

Rules:
- page_type: one of "instructions", "questions", "mixed", "diagram_only", "blank"
- is_needed_for_grading: true if page has questions, diagrams referenced by questions, or instructions
- Extract marks from patterns like "[5]", "(5 marks)", "5M"
- If no questions found, return empty questions_found array
- If page is blank/separator, set is_needed_for_grading to false"""

CONSOLIDATION_PROMPT = """Consolidate these page analyses into a unified question list for an exam.

TOTAL EXAM MARKS: {total_marks}

PAGE ANALYSES (one per page):
{page_analyses}

Return ONLY valid JSON (no markdown, no code blocks) with this exact structure:

{{
  "questions": [
    {{
      "q_no": "1",
      "question_text": "full consolidated question text",
      "marks": 5,
      "keywords": ["key1", "key2"],
      "has_diagram": false,
      "expected_answer": ""
    }}
  ],
  "marking_schemes": [
    {{
      "q_no": "1",
      "scheme_text": "marking scheme text"
    }}
  ],
  "total_marks_check": 100,
  "warnings": ["Any inconsistencies found"]
}}

Rules:
- Combine sub-parts into single question entries
- Merge question text that spans multiple pages
- Link marking schemes to their questions
- Extract keywords from question text for grading
- Set has_diagram=true if any visual element is associated with the question
- Sum of all question marks should equal total_marks (note any mismatch in warnings)"""


def _call_gemini_vision(image_path: str, prompt: str, model: str = COMPLEXITY_EXTRACTION_MODEL) -> str:
    """Send an image + prompt to Gemini and return the text response."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"

    parts = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime),
        types.Part.from_text(text=prompt),
    ]

    contents = [types.Content(role="user", parts=parts)]

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            http_options={"timeout": 300000},
        ),
    )

    if not response or not response.text:
        raise ValueError(f"Gemini returned empty response for text analysis. "
                        f"Finish reason: {getattr(response, 'finish_reason', 'unknown') if response else 'no response'}")

    return response.text


def _call_gemini_text(prompt: str, model: str = COMPLEXITY_EXTRACTION_MODEL) -> str:
    """Send a text-only prompt to Gemini and return the response."""
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            http_options={"timeout": 300000},
        ),
    )

    if not response or not response.text:
        raise ValueError(f"Gemini returned empty response for page analysis. "
                        f"Finish reason: {getattr(response, 'finish_reason', 'unknown') if response else 'no response'}")

    return response.text


def _clean_json_response(raw: str) -> str:
    """Strip markdown code fences if present."""
    if raw is None:
        raise ValueError("Received None response from AI")
    raw = raw.strip()
    if raw.startswith("```"):
        first_newline = raw.find("\n")
        if first_newline != -1:
            raw = raw[first_newline:]
        else:
            raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    return raw.strip()


def _analyze_page(args):
    """Worker function for parallel page analysis."""
    page_idx, image_path, exam_id = args
    page_no = page_idx + 1

    try:
        raw = _call_gemini_vision(image_path, PAGE_ANALYSIS_PROMPT)
        cleaned = _clean_json_response(raw)
        result = json.loads(cleaned)
        return page_no, result, None
    except Exception as e:
        return page_no, None, str(e)


_extraction_tasks: set = set()


async def start_extraction(exam_id: str, pdf_path: str, total_marks: int) -> str:
    """
    Start the extraction pipeline asynchronously.
    Returns the extraction_task_id.
    """
    output_dir = os.path.join(settings.STORAGE_PATH, "question_papers", exam_id)
    os.makedirs(output_dir, exist_ok=True)

    # Clear any existing task and question paper for this exam to allow re-upload
    await extraction_tasks_collection.delete_many({"exam_id": exam_id})
    await question_papers_collection.delete_many({"exam_id": exam_id})
    await answer_keys_collection.update_one(
        {"exam_id": exam_id},
        {"$set": {
            "question_paper_id": None,
            "included_page_refs": [],
            "excluded_page_refs": [],
            "questions": [],
            "source": "manual",
            "extraction_status": "none",
        }}
    )

    task_doc = {
        "exam_id": exam_id,
        "status": "rasterizing",
        "total_pages": 0,
        "processed_pages": 0,
        "current_page": 0,
        "current_step": "Converting PDF to images...",
        "questions_found_so_far": 0,
        "error": None,
        "started_at": time.time(),
        "completed_at": None,
    }

    task_result = await extraction_tasks_collection.insert_one(task_doc)
    task_id = str(task_result.inserted_id)

    task = asyncio.create_task(_run_extraction(exam_id, pdf_path, output_dir, total_marks, task_id))
    _extraction_tasks.add(task)
    task.add_done_callback(_extraction_tasks.discard)

    return task_id


async def _run_extraction(
    exam_id: str,
    pdf_path: str,
    output_dir: str,
    total_marks: int,
    task_id: str,
):
    """
    Full extraction pipeline:
    1. Rasterize PDF to page images
    2. Analyze each page with AI (parallel)
    3. Consolidate results
    4. Save to question_papers and answer_keys collections
    """
    try:
        await _update_task(task_id, status="rasterizing", current_step="Converting PDF to images...")

        page_infos = rasterize_pdf_to_pngs(pdf_path, output_dir, dpi=150)
        total_pages = len(page_infos)

        if total_pages == 0:
            await _update_task(
                task_id,
                status="failed",
                error="The PDF contains no pages. Please upload a valid question paper.",
                completed_at=time.time(),
            )
            return

        await _update_task(
            task_id,
            status="analyzing",
            total_pages=total_pages,
            current_step=f"Analyzing {total_pages} pages with AI...",
        )

        page_analyses = []
        tasks_for_worker = [(i, page_infos[i]["image_path"], exam_id) for i in range(total_pages)]

        failure_count = 0
        failure_threshold = max(2, total_pages // 2)
        max_workers = max(1, min(4, total_pages))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_analyze_page, t): t for t in tasks_for_worker}
            for future in concurrent.futures.as_completed(futures):
                page_no, result, error = future.result()
                if error:
                    failure_count += 1
                    print(f"[Extraction] Page {page_no} analysis failed: {error}")
                    page_analyses.append({
                        "page_no": page_no,
                        "analysis": {
                            "questions_found": [],
                            "is_instruction_page": False,
                            "instruction_text": "",
                            "marking_schemes": [],
                            "visual_elements": [],
                            "page_type": "blank",
                            "is_needed_for_grading": False,
                        },
                        "error": error,
                    })

                    if failure_count >= failure_threshold:
                        print(f"[Extraction] Too many failures ({failure_count}/{total_pages}). Aborting.")
                        for f in futures:
                            if not f.done():
                                f.cancel()
                            try:
                                f.result()
                            except (concurrent.futures.CancelledError, Exception):
                                pass
                        await _update_task(
                            task_id,
                            status="failed",
                            error=f"Extraction aborted: {failure_count}/{total_pages} pages failed. The model may be unavailable or the PDF is unreadable. Last error: {error}",
                            completed_at=time.time(),
                        )
                        return
                else:
                    page_analyses.append({
                        "page_no": page_no,
                        "analysis": result,
                        "error": None,
                    })

                processed = len(page_analyses)
                await _update_task(
                    task_id,
                    processed_pages=processed,
                    current_page=page_no,
                    current_step=f"Analyzed {processed}/{total_pages} pages...",
                )

        page_analyses.sort(key=lambda x: x["page_no"])

        await _update_task(
            task_id,
            status="consolidating",
            current_step="Consolidating results across all pages...",
        )

        analyses_text = ""
        for pa in page_analyses:
            analyses_text += f"\n--- Page {pa['page_no']} ---\n{json.dumps(pa['analysis'], indent=2)}\n"

        consolidation_prompt = CONSOLIDATION_PROMPT.format(
            total_marks=total_marks,
            page_analyses=analyses_text,
        )

        raw = _call_gemini_text(consolidation_prompt)
        cleaned = _clean_json_response(raw)
        consolidated = json.loads(cleaned)

        questions = consolidated.get("questions", [])
        marking_schemes = consolidated.get("marking_schemes", [])
        warnings = consolidated.get("warnings", [])

        await _update_task(
            task_id,
            questions_found_so_far=len(questions),
        )

        pages_data = []
        for pa in page_analyses:
            analysis = pa["analysis"]
            info = next((p for p in page_infos if p["page_no"] == pa["page_no"]), {})
            pages_data.append({
                "page_no": pa["page_no"],
                "image_path": info.get("image_path", ""),
                "is_instruction_page": analysis.get("is_instruction_page", False),
                "has_questions": len(analysis.get("questions_found", [])) > 0,
                "has_diagrams": any(ve.get("type") == "diagram" for ve in analysis.get("visual_elements", [])),
                "has_graphs": any(ve.get("type") == "graph" for ve in analysis.get("visual_elements", [])),
                "is_needed_for_grading": analysis.get("is_needed_for_grading", False),
                "reason": _build_page_reason(pa["page_no"], analysis),
            })

        included_refs = [p["page_no"] for p in pages_data if p["is_needed_for_grading"]]
        excluded_refs = [p["page_no"] for p in pages_data if not p["is_needed_for_grading"]]

        extracted_questions = []
        for q in questions:
            scheme = next((s for s in marking_schemes if s.get("q_no") == q.get("q_no")), None)
            extracted_questions.append({
                "q_no": q.get("q_no", ""),
                "question": q.get("question_text"),
                "question_page_refs": [],
                "expected_answer": q.get("expected_answer", ""),
                "marks": q.get("marks", 0),
                "keywords": q.get("keywords", []),
                "marking_scheme": scheme.get("scheme_text") if scheme else None,
                "marking_scheme_page_ref": None,
                "has_diagram": q.get("has_diagram", False),
                "diagram_page_refs": [],
            })

        qp_doc = {
            "exam_id": exam_id,
            "source_file": pdf_path,
            "total_pages": total_pages,
            "pages": pages_data,
            "extracted_questions": extracted_questions,
            "status": "extracted",
            "extraction_model": COMPLEXITY_EXTRACTION_MODEL,
            "warnings": warnings,
            "created_at": time.time(),
            "updated_at": time.time(),
        }

        qp_result = await question_papers_collection.insert_one(qp_doc)
        qp_id = str(qp_result.inserted_id)

        await answer_keys_collection.update_one(
            {"exam_id": exam_id},
            {
                "$set": {
                    "question_paper_id": qp_id,
                    "questions": extracted_questions,
                    "source": "ai_extracted",
                    "extraction_status": "completed",
                },
                "$setOnInsert": {
                    "exam_id": exam_id,
                    "included_page_refs": included_refs,
                    "excluded_page_refs": excluded_refs,
                    "sample_sheets": [],
                    "created_at": time.time(),
                },
            },
            upsert=True,
        )

        await _update_task(
            task_id,
            status="completed",
            current_step="Extraction complete!",
            completed_at=time.time(),
        )

    except Exception as e:
        error_msg = str(e)
        # Make common errors user-friendly
        if "NOT_FOUND" in error_msg and "model" in error_msg.lower():
            error_msg = "AI model is currently unavailable. Please try again later or contact support."
        elif "empty response" in error_msg.lower():
            error_msg = "AI returned an empty response. The PDF page may be blank or unreadable. Try a higher quality PDF."
        elif "403" in error_msg or "permission" in error_msg.lower():
            error_msg = "AI access denied. Check your API key configuration."
        elif "quota" in error_msg.lower() or "rate" in error_msg.lower():
            error_msg = "AI service rate limit exceeded. Please wait a few minutes and try again."

        await _update_task(
            task_id,
            status="failed",
            error=f"Extraction failed: {error_msg}",
            completed_at=time.time(),
        )
        print(f"[Extraction] Failed for exam {exam_id}: {e}")


def _build_page_reason(page_no: int, analysis: dict) -> str:
    """Build a human-readable reason for page inclusion."""
    questions = analysis.get("questions_found", [])
    visual = analysis.get("visual_elements", [])

    if analysis.get("is_instruction_page"):
        return "General instructions page"
    if analysis.get("page_type") == "blank":
        return "Blank/separator page"
    if len(questions) > 0:
        q_nos = [q.get("q_no", "?") for q in questions]
        has_diagrams = any(ve.get("type") in ("diagram", "graph") for ve in visual)
        desc = f"Contains Q{', Q'.join(q_nos)}"
        if has_diagrams:
            desc += " with diagrams"
        return desc
    if visual:
        types = set(ve.get("type", "unknown") for ve in visual)
        return f"Contains {', '.join(types)}"
    return "Unclassified"


async def _update_task(task_id: str, **kwargs):
    """Update extraction task in database."""
    if kwargs:
        await extraction_tasks_collection.update_one(
            {"_id": bson.ObjectId(task_id)},
            {"$set": kwargs},
        )


async def get_extraction_status(task_id: str) -> Optional[Dict[str, Any]]:
    """Get extraction task status."""
    task = await extraction_tasks_collection.find_one({"_id": bson.ObjectId(task_id)})
    if not task:
        return None

    return {
        "id": str(task["_id"]),
        "exam_id": task["exam_id"],
        "status": task.get("status", "pending"),
        "total_pages": task.get("total_pages", 0),
        "processed_pages": task.get("processed_pages", 0),
        "current_page": task.get("current_page", 0),
        "current_step": task.get("current_step", ""),
        "questions_found_so_far": task.get("questions_found_so_far", 0),
        "error": task.get("error"),
        "started_at": task.get("started_at"),
        "completed_at": task.get("completed_at"),
    }


async def get_question_paper(exam_id: str) -> Optional[Dict[str, Any]]:
    """Get question paper for an exam."""
    qp = await question_papers_collection.find_one({"exam_id": exam_id})
    if not qp:
        return None

    return {
        "id": str(qp["_id"]),
        "exam_id": qp["exam_id"],
        "source_file": qp["source_file"],
        "total_pages": qp["total_pages"],
        "pages": qp.get("pages", []),
        "extracted_questions": qp.get("extracted_questions", []),
        "status": qp.get("status", "pending_extraction"),
        "extraction_model": qp.get("extraction_model"),
        "warnings": qp.get("warnings", []),
        "created_at": qp.get("created_at"),
        "updated_at": qp.get("updated_at"),
    }


async def update_question_paper_review(
    exam_id: str,
    included_page_refs: List[int],
    excluded_page_refs: List[int],
    questions: Optional[List[dict]] = None,
) -> bool:
    """Update question paper review: confirm pages and edit questions."""
    qp = await question_papers_collection.find_one({"exam_id": exam_id})
    if not qp:
        return False

    updates = {
        "included_page_refs": included_page_refs,
        "excluded_page_refs": excluded_page_refs,
        "updated_at": time.time(),
    }

    if questions is not None:
        updates["extracted_questions"] = questions
        updates["status"] = "reviewed"

    await question_papers_collection.update_one(
        {"_id": qp["_id"]},
        {"$set": updates},
    )

    await answer_keys_collection.update_one(
        {"exam_id": exam_id},
        {"$set": {
            "included_page_refs": included_page_refs,
            "excluded_page_refs": excluded_page_refs,
            "questions": questions if questions is not None else qp.get("extracted_questions", []),
        }},
    )

    return True
