import os
import json
import asyncio
import queue
import mimetypes
import time
from typing import Optional, Dict, Any, List, Tuple
from google import genai
from google.genai import types
from core.config import settings


ProgressQueueItem = Tuple[int, int, str]


def _detect_mime_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".pdf": "application/pdf",
        ".jsonl": "application/jsonl",
        ".json": "application/json",
    }
    return mime_map.get(ext, "application/octet-stream")


def _retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                time.sleep(delay)
    raise last_error


class GeminiBatchAdapter:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def upload_image(self, image_path: str) -> str:
        def _do_upload():
            uploaded_file = self.client.files.upload(
                file=image_path,
                config=types.UploadFileConfig(
                    display_name=os.path.basename(image_path),
                    mime_type=_detect_mime_type(image_path),
                ),
            )
            return uploaded_file.name

        return _retry_with_backoff(_do_upload)

    def upload_jsonl(self, jsonl_path: str) -> str:
        def _do_upload():
            uploaded_file = self.client.files.upload(
                file=jsonl_path,
                config=types.UploadFileConfig(
                    display_name=f"batch-input-{os.path.basename(jsonl_path)}",
                    mime_type="application/jsonl",
                ),
            )
            return uploaded_file.name

        return _retry_with_backoff(_do_upload)

    def upload_files_for_batch(
        self,
        input_jsonl_path: str,
        batch_id: str,
        progress_queue: Optional[queue.Queue] = None,
    ) -> Tuple[str, List[str]]:
        print(f"[DEBUG] Starting upload for batch {batch_id}")
        print(f"[DEBUG] Input JSONL path: {input_jsonl_path}")
        
        with open(input_jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        print(f"[DEBUG] Read {len(lines)} JSONL lines")

        unique_paths = set()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            request = entry.get("request", {})
            contents = request.get("contents", [])
            for content in contents:
                for part in content.get("parts", []):
                    if "_file_ref" in part:
                        fp = part["_file_ref"]
                        if os.path.exists(fp):
                            unique_paths.add(fp)

        total_unique = len(unique_paths)
        print(f"[DEBUG] Found {total_unique} unique file paths to upload")

        file_uri_map = {}
        uploaded_files = []

        for idx, file_path in enumerate(sorted(unique_paths)):
            print(f"[DEBUG] Uploading file {idx + 1}/{total_unique}: {file_path}")
            uploaded_name = self.upload_image(file_path)
            file_uri_map[file_path] = uploaded_name
            uploaded_files.append(uploaded_name)
            if progress_queue:
                progress_queue.put((idx + 1, total_unique, f"Uploading images ({idx + 1}/{total_unique})..."))

        if progress_queue:
            progress_queue.put((total_unique, total_unique, "Building JSONL with file URIs..."))

        new_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if "custom_id" not in entry and "key" in entry:
                entry["custom_id"] = entry["key"]
            request = entry.get("request", {})
            contents = request.get("contents", [])
            for content in contents:
                parts = content.get("parts", [])
                for i, part in enumerate(parts):
                    if "_file_ref" in part:
                        fp = part["_file_ref"]
                        if fp in file_uri_map:
                            uri = file_uri_map[fp]
                            if not uri.startswith("http"):
                                uri = f"https://generativelanguage.googleapis.com/{uri}"
                            parts[i] = {
                                "file_data": {
                                    "mime_type": _detect_mime_type(fp),
                                    "file_uri": uri,
                                }
                            }
                        else:
                            parts[i] = {"text": f"[Image not found: {fp}]"}
            new_lines.append(json.dumps(entry, ensure_ascii=False))

        output_path = os.path.join(
            settings.STORAGE_PATH,
            "batches",
            str(batch_id),
            "input_with_uris.jsonl",
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for new_line in new_lines:
                f.write(new_line + "\n")

        if progress_queue:
            progress_queue.put((1, 1, "Uploading JSONL to Gemini..."))

        return output_path, uploaded_files

    def submit(self, model: str, input_jsonl_path: str) -> str:
        uploaded_file_name = self.upload_jsonl(input_jsonl_path)

        batch_job = self.client.batches.create(
            model=model,
            src=uploaded_file_name,
        )

        return batch_job.name

    def get_status(self, provider_batch_id: str) -> Dict[str, Any]:
        job = self.client.batches.get(name=provider_batch_id)

        state_map = {
            "JOB_STATE_QUEUED": "in_progress",
            "JOB_STATE_PENDING": "submitted",
            "JOB_STATE_RUNNING": "in_progress",
            "JOB_STATE_SUCCEEDED": "completed",
            "JOB_STATE_FAILED": "failed",
            "JOB_STATE_CANCELLED": "cancelled",
            "JOB_STATE_PAUSED": "in_progress",
        }

        status = state_map.get(job.state.name, "in_progress")
        completed = job.request_count if hasattr(job, "request_count") else 0
        total = job.total_count if hasattr(job, "total_count") else 0
        failed = job.failed_count if hasattr(job, "failed_count") else 0

        output_file_name = None
        if status == "completed" and hasattr(job, "dest") and job.dest:
            if hasattr(job.dest, "file_name"):
                output_file_name = job.dest.file_name

        return {
            "status": status,
            "completed_count": completed,
            "failed_count": failed,
            "total_count": total,
            "output_file_name": output_file_name,
            "error": str(job.error) if hasattr(job, "error") and job.error else None,
        }

    def download_output(self, provider_batch_id: str, dest_path: str) -> str:
        job = self.client.batches.get(name=provider_batch_id)

        if not hasattr(job, "dest") or not job.dest or not hasattr(job.dest, "file_name"):
            raise ValueError("No output file available for this batch job")

        output_file_name = job.dest.file_name
        file_content_bytes = self.client.files.download(file=output_file_name)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(file_content_bytes)

        return dest_path

    def cancel(self, provider_batch_id: str) -> bool:
        try:
            self.client.batches.cancel(name=provider_batch_id)
            return True
        except Exception:
            return False


class OpenAIBatchAdapter:
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def submit(self, model: str, input_jsonl_path: str) -> str:
        with open(input_jsonl_path, "rb") as f:
            batch_input_file = self.client.files.create(file=f, purpose="batch")

        batch_job = self.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )

        return batch_job.id

    def get_status(self, provider_batch_id: str) -> Dict[str, Any]:
        batch_job = self.client.batches.retrieve(provider_batch_id)

        status_map = {
            "validating": "submitted",
            "in_progress": "in_progress",
            "finalizing": "in_progress",
            "completed": "completed",
            "failed": "failed",
            "expired": "expired",
            "cancelled": "cancelled",
        }

        status = status_map.get(batch_job.status, "in_progress")
        completed = batch_job.request_counts.completed if batch_job.request_counts else 0
        failed = batch_job.request_counts.failed if batch_job.request_counts else 0
        total = batch_job.request_counts.total if batch_job.request_counts else 0

        output_file_id = batch_job.output_file_id if hasattr(batch_job, "output_file_id") else None

        return {
            "status": status,
            "completed_count": completed,
            "failed_count": failed,
            "total_count": total,
            "output_file_id": output_file_id,
            "error": batch_job.errors.data[0].message if batch_job.errors and batch_job.errors.data else None,
        }

    def download_output(self, provider_batch_id: str, dest_path: str) -> str:
        batch_job = self.client.batches.retrieve(provider_batch_id)

        if not batch_job.output_file_id:
            raise ValueError("No output file available for this batch job")

        response = self.client.files.content(batch_job.output_file_id)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(response.content)

        return dest_path

    def cancel(self, provider_batch_id: str) -> bool:
        try:
            self.client.batches.cancel(provider_batch_id)
            return True
        except Exception:
            return False


_adapters = {}


def get_adapter(provider: str):
    if provider not in _adapters:
        if provider == "gemini":
            _adapters[provider] = GeminiBatchAdapter()
        elif provider == "openai":
            _adapters[provider] = OpenAIBatchAdapter()
        else:
            raise ValueError(f"Unknown provider: {provider}")
    return _adapters[provider]


async def upload_files_for_batch(
    provider: str,
    input_jsonl_path: str,
    batch_id: str,
    progress_queue: Optional[queue.Queue] = None,
) -> Tuple[str, List[str]]:
    adapter = get_adapter(provider)
    if provider == "gemini":
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: adapter.upload_files_for_batch(input_jsonl_path, batch_id, progress_queue)
        )
    else:
        return input_jsonl_path, []


async def submit_batch(provider: str, model: str, input_jsonl_path: str) -> str:
    adapter = get_adapter(provider)
    return adapter.submit(model, input_jsonl_path)


async def poll_batch(provider: str, provider_batch_id: str) -> Dict[str, Any]:
    adapter = get_adapter(provider)
    return adapter.get_status(provider_batch_id)


async def download_output(provider: str, provider_batch_id: str, dest_path: str) -> str:
    adapter = get_adapter(provider)
    return adapter.download_output(provider_batch_id, dest_path)


async def cancel_batch(provider: str, provider_batch_id: str) -> bool:
    adapter = get_adapter(provider)
    return adapter.cancel(provider_batch_id)
