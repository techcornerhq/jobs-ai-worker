from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

MODEL_PATH = os.getenv("QWEN_MODEL_PATH", "models/Qwen3-4B-Q4_K_M.gguf").strip()
LLAMA_CLI = os.getenv("LLAMA_CLI", "llama-cli")
MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "850"))
CTX = int(os.getenv("QWEN_CTX", "4096"))
TEMP = os.getenv("QWEN_TEMP", "0.15")
THREADS = os.getenv("QWEN_THREADS", "4")

MISSING = "غير مذكور في الإعلان"

SYSTEM_RULES = f"""
أنت محرر وظائف عربي دقيق لموقع وظائف الأردن. حوّل بيانات الإعلان إلى JSON مختصر ومفيد.

قواعد إلزامية:
1) ممنوع اختلاق أي حقيقة رسمية: الشركة، الراتب، الموقع، الموعد، المؤهل، الخبرة، عدد الشواغر أو طريقة التقديم.
2) إذا لم تجد المعلومة مدعومة بالنص فاكتب: {MISSING}
3) أي راتب مكتوب كـ"متوقع" أو "تقديري" في مصدر تجميعي ليس راتباً رسمياً.
4) النصائح العامة توضع فقط داخل general_guidance ولا تُنسب للشركة.
5) لا تنسخ فقرات المصدر حرفياً؛ أعد تنظيم الحقائق بإيجاز.
6) لا ترفض الوظيفة بسبب نقص المعلومات.
7) seo_title طبيعي وغير مضلل، وmeta_description موجز.
8) labels بحد أقصى 5.
9) schema_supported_fields يحتوي فقط حقولاً مدعومة فعلاً.
10) أخرج JSON فقط، بدون Markdown أو شرح خارجي.
11) استخدم العربية الفصحى المبسطة المناسبة للأردن.
/no_think
""".strip()

OUTPUT_SHAPE = {
    "seo_title": "",
    "meta_description": "",
    "summary": "",
    "official_details": {
        "employer": MISSING,
        "job_title": MISSING,
        "location": MISSING,
        "salary": MISSING,
        "employment_type": MISSING,
        "experience": MISSING,
        "qualification": MISSING,
        "application_method": MISSING,
        "deadline": MISSING,
    },
    "official_requirements": [],
    "official_duties": [],
    "missing_official_information": [],
    "general_guidance": {
        "skills_that_may_help": [],
        "cv_tips": [],
        "before_applying": [],
    },
    "safety_note": "",
    "verification_notes": [],
    "labels": [],
    "schema_supported_fields": [],
}


def compact_source_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value[:limit]


def prompt_for(job: dict) -> str:
    # Deliberately send only fields that can materially change the editorial result.
    # This keeps CPU prompt-evaluation time low on free GitHub runners.
    compact_job = {
        "title": job.get("title"),
        "page_title": job.get("page_title"),
        "source_name": job.get("source_name"),
        "source_discovery_url": job.get("source_discovery_url"),
        "source_original_url": job.get("source_original_url"),
        "source_original_fetch_ok": job.get("source_original_fetch_ok"),
        "application_email": job.get("application_email"),
        "application_phone": job.get("application_phone"),
        "application_url": job.get("application_url"),
        "dates_found": job.get("dates_found", [])[:8],
        "feed_published": job.get("feed_published"),
        "country": job.get("country", "Jordan"),
        "original_text": compact_source_text(job.get("original_text"), 5000),
        "discovery_text": compact_source_text(job.get("discovery_text"), 3500),
    }
    payload = {"job": compact_job, "required_output_shape": OUTPUT_SHAPE}
    return SYSTEM_RULES + "\n\nINPUT_JSON:\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("Qwen output did not contain a JSON object")
    candidate = text[start:end + 1]
    try:
        result = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from Qwen: {exc}: {candidate[:1200]}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Qwen JSON root is not an object")
    return result


def run_qwen(job: dict) -> dict:
    model = Path(MODEL_PATH)
    if not model.exists():
        raise RuntimeError(f"Qwen model not found: {model}")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as f:
        f.write(prompt_for(job))
        prompt_path = f.name

    try:
        cmd = [
            LLAMA_CLI,
            "-m", str(model),
            "-f", prompt_path,
            "-c", str(CTX),
            "-n", str(MAX_TOKENS),
            "--temp", str(TEMP),
            "-t", str(THREADS),
            "-tb", str(THREADS),
            "--no-warmup",
            "--no-display-prompt",
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=1200)
        if proc.returncode != 0:
            raise RuntimeError(f"llama-cli failed ({proc.returncode}): {proc.stderr[-4000:]}")
        result = extract_json(proc.stdout)
        result["ai_provider"] = "local_qwen_llama_cpp"
        result["ai_model"] = model.name
        result["paid_api_used"] = False
        return result
    finally:
        Path(prompt_path).unlink(missing_ok=True)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input_json")
    parser.add_argument("output_json")
    args = parser.parse_args()
    job = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    result = run_qwen(job)
    out = Path(args.output_json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out)
