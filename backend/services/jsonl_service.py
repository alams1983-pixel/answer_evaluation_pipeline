import json
import os
import base64
from typing import List, Optional
from core.config import settings

UNIVERSAL_RESULT_SCHEMA = {
    "type": "object",
    "required": ["student", "total_max", "total_awarded", "questions"],
    "properties": {
        "student": {
            "type": "object",
            "required": ["name", "roll_no", "class"],
            "properties": {
                "name": {"type": "string", "description": "Student full name"},
                "roll_no": {"type": "string", "description": "Roll number"},
                "class": {"type": "string", "description": "Class/section"}
            }
        },
        "subject": {"type": "string", "description": "Subject name"},
        "exam_title": {"type": "string", "description": "Exam title"},
        "total_max": {"type": "number", "minimum": 0, "description": "Maximum possible marks"},
        "total_awarded": {"type": "number", "minimum": 0, "description": "Total marks awarded"},
        "percentage": {"type": "number", "minimum": 0, "maximum": 100, "description": "Percentage score"},
        "grade": {"type": "string", "description": "Grade awarded"},
        "overall_feedback": {"type": "string", "description": "General evaluation feedback for student"},
        "remedial_topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Topics recommended for revision"
        },
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["q_no", "awarded", "max"],
                "properties": {
                    "q_no": {"type": "string", "description": "Question number/identifier"},
                    "max": {"type": "number", "minimum": 0, "description": "Maximum marks for question"},
                    "awarded": {"type": "number", "minimum": 0, "description": "Marks awarded"},
                    "feedback": {"type": "string", "description": "Question-specific feedback"},
                    "page_refs": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Page numbers where question appears"
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "AI confidence score (0-1)"},
                    "error_type": {"type": "string", "description": "Error category if any (conceptual, calculation, incomplete)"}
                }
            },
            "description": "Per-question evaluation breakdown"
        }
    }
}


def build_jsonl_line_gemini(
    sheet_id: str,
    student_name: str,
    roll_no: str,
    class_label: str,
    subject: str,
    page_image_paths: List[str],
    answer_key_questions: List[dict],
    sample_sheets: List[dict],
    result_schema: Optional[dict] = None,
    qp_page_paths: Optional[List[str]] = None,
    complexity_tier: str = "standard",
) -> str:
    target_schema = result_schema if (result_schema and isinstance(result_schema, dict) and len(result_schema) > 0) else UNIVERSAL_RESULT_SCHEMA

    parts = []

    tier_instructions = {
        "simple": "Grade based on basic correctness. Award marks for key concepts and keywords. Be straightforward in evaluation.",
        "standard": "Grade with moderate rigor. Consider partial credit for partially correct answers. Evaluate reasoning and completeness.",
        "complex": "Grade with high rigor. Evaluate depth of understanding, multi-step reasoning, diagram/graph interpretation. Award marks only for complete and correct solutions.",
    }
    instruction = tier_instructions.get(complexity_tier, tier_instructions["standard"])

    parts.append({
        "text": f"You are grading a handwritten answer sheet. Complexity level: {complexity_tier}. {instruction} Follow the rubric and answer key. Return JSON strictly matching the provided schema."
    })

    parts.append({
        "text": f"Student: {student_name} | Roll: {roll_no} | Class: {class_label} | Subject: {subject}"
    })

    if qp_page_paths:
        parts.append({"text": "Question paper pages (for context, diagrams, and marking schemes):"})
        for qp_path in qp_page_paths:
            if os.path.exists(qp_path):
                parts.append({"_file_ref": qp_path})

    if answer_key_questions:
        parts.append({"text": "Answer key and grading rubric:"})
        for q in answer_key_questions:
            q_no = q.get("q_no", "?")
            q_text = q.get("question", "")
            marks = q.get("marks", 0)
            expected = q.get("expected_answer", "")
            marking_scheme = q.get("marking_scheme", "")
            keywords = q.get("keywords", [])

            q_summary_parts = []
            q_summary_parts.append(f"Q{q_no} ({marks} marks): {q_text}")
            if expected:
                q_summary_parts[-1] += f" Expected: {expected}"
            if marking_scheme:
                q_summary_parts[-1] += f" Marking: {marking_scheme}"
            if keywords:
                q_summary_parts[-1] += f" Keywords: {', '.join(keywords)}"

            parts.append({"text": q_summary_parts[-1]})

            attached_images = q.get("attached_images", [])
            if attached_images:
                parts.append({"text": f"  Reference images for Q{q_no}:"})
                for img in attached_images:
                    img_path = img.get("image_path", "")
                    if img_path and os.path.exists(img_path):
                        parts.append({"_file_ref": img_path})
                    label = img.get("label", "")
                    if label:
                        parts.append({"text": f"  ({label})"})

    for sample in sample_sheets:
        kind = sample.get("kind", "")
        path = sample.get("path", "")
        label = sample.get("label", "")
        notes = sample.get("notes", "")

        if kind == "text" and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                text_content = f.read()
            parts.append({"text": f"Sample model sheet (label: {label}): {text_content}"})
            if notes:
                parts.append({"text": f"Sample notes: {notes}"})
        elif kind in ("image", "pdf") and os.path.exists(path):
            parts.append({"_file_ref": path})
            parts.append({"text": f"Sample model sheet (label: {label}, kind: {kind})"})
            if notes:
                parts.append({"text": f"Sample notes: {notes}"})

    parts.append({"text": "Student answer sheet pages:"})

    for img_path in page_image_paths:
        if os.path.exists(img_path):
            parts.append({"_file_ref": img_path})

    parts.append({
        "text": f"Respond with JSON ONLY conforming to schema: {json.dumps(target_schema)}"
    })

    contents = [
        {
            "parts": parts,
        }
    ]

    request = {
        "contents": contents,
    }

    line = {
        "custom_id": f"sheet_{sheet_id}",
        "key": f"sheet_{sheet_id}",
        "request": request,
    }

    return json.dumps(line, ensure_ascii=False)


def build_jsonl_line_openai(
    sheet_id: str,
    student_name: str,
    roll_no: str,
    class_label: str,
    subject: str,
    page_image_paths: List[str],
    answer_key_questions: List[dict],
    sample_sheets: List[dict],
    result_schema: Optional[dict] = None,
    model: str = "gpt-4.1-mini",
) -> str:
    target_schema = result_schema if (result_schema and isinstance(result_schema, dict) and len(result_schema) > 0) else UNIVERSAL_RESULT_SCHEMA
    content_parts = []


    content_parts.append({
        "type": "text",
        "text": "You are grading a handwritten answer sheet. Follow the rubric and answer key. Return JSON strictly matching the provided schema."
    })

    content_parts.append({
        "type": "text",
        "text": f"Student: {student_name} | Roll: {roll_no} | Class: {class_label} | Subject: {subject}"
    })

    if answer_key_questions:
        content_parts.append({
            "type": "text",
            "text": "Answer key and grading rubric:"
        })
        for q in answer_key_questions:
            q_no = q.get("q_no", "?")
            q_text = q.get("question", "")
            marks = q.get("marks", 0)
            expected = q.get("expected_answer", "")
            marking_scheme = q.get("marking_scheme", "")
            keywords = q.get("keywords", [])

            q_summary = f"Q{q_no} ({marks} marks): {q_text}"
            if expected:
                q_summary += f" Expected: {expected}"
            if marking_scheme:
                q_summary += f" Marking: {marking_scheme}"
            if keywords:
                q_summary += f" Keywords: {', '.join(keywords)}"

            content_parts.append({
                "type": "text",
                "text": q_summary
            })

            attached_images = q.get("attached_images", [])
            if attached_images:
                content_parts.append({
                    "type": "text",
                    "text": f"  Reference images for Q{q_no}:"
                })
                for img in attached_images:
                    img_path = img.get("image_path", "")
                    if img_path and os.path.exists(img_path):
                        with open(img_path, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("utf-8")
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}"
                            }
                        })
                    label = img.get("label", "")
                    if label:
                        content_parts.append({
                            "type": "text",
                            "text": f"  ({label})"
                        })

    for sample in sample_sheets:
        kind = sample.get("kind", "")
        path = sample.get("path", "")
        label = sample.get("label", "")
        notes = sample.get("notes", "")

        if kind == "text" and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                text_content = f.read()
            content_parts.append({
                "type": "text",
                "text": f"Sample model sheet (label: {label}): {text_content}"
            })
            if notes:
                content_parts.append({
                    "type": "text",
                    "text": f"Sample notes: {notes}"
                })
        elif kind == "image" and os.path.exists(path):
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64}"
                }
            })
            content_parts.append({
                "type": "text",
                "text": f"Sample model sheet (label: {label}, kind: {kind})"
            })
            if notes:
                content_parts.append({
                    "type": "text",
                    "text": f"Sample notes: {notes}"
                })

    content_parts.append({
        "type": "text",
        "text": "Student answer sheet pages:"
    })

    for img_path in page_image_paths:
        if os.path.exists(img_path):
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64}"
                }
            })

    schema_prompt = f"Respond with JSON ONLY conforming to schema: {json.dumps(target_schema)}"
    content_parts.append({
        "type": "text",
        "text": schema_prompt
    })

    messages = [
        {
            "role": "user",
            "content": content_parts,
        }
    ]

    request = {
        "model": model,
        "messages": messages,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "grading_result",
                "schema": target_schema,
            },
        },
    }


    line = {
        "custom_id": f"sheet_{sheet_id}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": request,
    }

    return json.dumps(line, ensure_ascii=False)


def build_jsonl_line(
    sheet_id: str,
    student_name: str,
    roll_no: str,
    class_label: str,
    subject: str,
    page_image_paths: List[str],
    answer_key_questions: List[dict],
    sample_sheets: List[dict],
    result_schema: dict,
    provider: str = "gemini",
    model: str = "gemini-2.5-flash",
    qp_page_paths: Optional[List[str]] = None,
    complexity_tier: str = "standard",
) -> str:
    if provider == "openai":
        return build_jsonl_line_openai(
            sheet_id=sheet_id,
            student_name=student_name,
            roll_no=roll_no,
            class_label=class_label,
            subject=subject,
            page_image_paths=page_image_paths,
            answer_key_questions=answer_key_questions,
            sample_sheets=sample_sheets,
            result_schema=result_schema,
            model=model,
        )
    else:
        return build_jsonl_line_gemini(
            sheet_id=sheet_id,
            student_name=student_name,
            roll_no=roll_no,
            class_label=class_label,
            subject=subject,
            page_image_paths=page_image_paths,
            answer_key_questions=answer_key_questions,
            sample_sheets=sample_sheets,
            result_schema=result_schema,
            qp_page_paths=qp_page_paths,
            complexity_tier=complexity_tier,
        )


def write_batch_input(batch_id: str, lines: List[str]) -> str:
    batch_dir = os.path.join(settings.STORAGE_PATH, "batches", str(batch_id))
    os.makedirs(batch_dir, exist_ok=True)

    output_path = os.path.join(batch_dir, "input.jsonl")
    with open(output_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

    return output_path


def parse_batch_output(output_file: str) -> List[dict]:
    results = []
    with open(output_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                result = json.loads(line)
                results.append(result)
            except json.JSONDecodeError:
                results.append({"raw": line, "parse_error": True})
    return results
