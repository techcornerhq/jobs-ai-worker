from __future__ import annotations

import json
import os
import re

import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "950"))
TEMP = float(os.getenv("QWEN_TEMP", "0.20"))
MISSING = "غير مذكور في الإعلان"

SYSTEM_RULES = f"""
أنت محرر وظائف عربي دقيق لموقع وظائف الأردن. حوّل بيانات الإعلان إلى JSON منظم ومفيد للنشر.

قواعد إلزامية:
1) ممنوع اختلاق أي حقيقة رسمية: الشركة، الراتب، الموقع، الموعد، المؤهل، الخبرة، عدد الشواغر أو طريقة التقديم.
2) إذا لم تجد المعلومة مدعومة بالنص فاكتب حرفياً: {MISSING}
3) المصدر التجميعي ليس مصدراً رسمياً. أي راتب مكتوب كـ«متوقع» أو «تقديري» لا يصبح راتباً رسمياً إلا إذا أكده المصدر الأصلي.
4) إذا تعارض discovery_text مع original_text ففضّل original_text واذكر التعارض في verification_notes.
5) النصائح العامة توضع فقط داخل general_guidance ولا تُنسب إلى جهة التوظيف.
6) لا تنسخ فقرات المصدر حرفياً؛ أعد تنظيم الحقائق بإيجاز وبصياغة عربية طبيعية.
7) لا ترفض الوظيفة بسبب نقص المعلومات.
8) seo_title طبيعي وغير مضلل ولا يذكر راتباً غير رسمي.
9) labels بحد أقصى 5، وschema_supported_fields يحتوي فقط حقولاً مدعومة فعلاً.
10) أخرج JSON فقط بدون Markdown أو شرح خارجي.
11) استخدم العربية الفصحى المبسطة المناسبة للأردن.
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
        "original_text": compact_source_text(job.get("original_text"), 9000),
        "discovery_text": compact_source_text(job.get("discovery_text"), 5000),
    }
    return json.dumps({"job": compact_job, "required_output_shape": OUTPUT_SHAPE}, ensure_ascii=False)


def extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError("Groq/Qwen output did not contain a JSON object")
    try:
        result = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from Groq/Qwen: {exc}") from exc
    if not isinstance(result, dict):
        raise RuntimeError("Groq/Qwen JSON root is not an object")
    return result


def run_qwen(job: dict) -> dict:
    if not GROQ_API_KEY:
        raise RuntimeError("Missing GROQ_API_KEY secret")

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_RULES},
            {"role": "user", "content": prompt_for(job)},
        ],
        "temperature": TEMP,
        "max_completion_tokens": MAX_TOKENS,
        "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
    }
    r = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if not r.ok:
        raise RuntimeError(f"Groq API failed HTTP {r.status_code}: {r.text[:1800]}")

    data = r.json()
    content = data["choices"][0]["message"]["content"]
    result = extract_json(content)
    usage = data.get("usage") or {}
    result["ai_provider"] = "groq_free_plan"
    result["ai_model"] = GROQ_MODEL
    result["paid_api_used"] = False
    result["paid_fallback_used"] = False
    result["usage"] = {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
    }
    return result


if __name__ == "__main__":
    import argparse
    from pathlib import Path

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
