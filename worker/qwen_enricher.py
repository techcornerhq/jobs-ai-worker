from __future__ import annotations

import json
import os
import re
import time

import requests

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "950"))
TEMP = float(os.getenv("QWEN_TEMP", "0.20"))
MISSING = "غير مذكور في الإعلان"
MAX_RATE_LIMIT_RETRIES = int(os.getenv("GROQ_RATE_LIMIT_RETRIES", "3"))

SYSTEM_RULES = f"""
أنت محرر وظائف عربي دقيق لموقع وظائف الأردن. حوّل بيانات الإعلان إلى JSON منظم ومفيد للنشر، مع عنوان جذاب غير مضلل وقيمة تحريرية حقيقية للباحث عن عمل.

قواعد إلزامية:
1) ممنوع اختلاق أي حقيقة رسمية: الشركة، الراتب، الموقع، الموعد، المؤهل، الخبرة، عدد الشواغر أو طريقة التقديم.
2) إذا لم تجد حقيقة رسمية مدعومة بالنص فاكتب حرفياً: {MISSING}
3) إذا ورد راتب أو نطاق راتب صراحة في نص الإعلان التجميعي بصيغة «متوقع» أو «تقديري»، احتفظ بالمعلومة ولا تحذفها. يجوز ذكرها في seo_title أو social_title أو meta_description أو summary فقط بصياغة واضحة مثل «راتب متوقع 300–600 دينار» أو «تقدير راتب 300–600 دينار». لا تحوّلها إلى راتب رسمي في official_details.salary إلا إذا أكدها المصدر الأصلي أو جهة التوظيف.
4) إذا ورد رقم راتب في المصدر الأصلي أو الرسمي بدون وصفه كتقديري، عامله كمعلومة راتب رسمية مدعومة.
5) إذا تعارض discovery_text مع original_text ففضّل original_text في الحقائق الرسمية واذكر التعارض باختصار في verification_notes، مع السماح بالاحتفاظ بالمعلومة التجميعية المنفصلة إذا كانت موسومة بوضوح كتقديرية.
6) لا تنسخ فقرات المصدر حرفياً؛ أعد تنظيم الحقائق بصياغة عربية طبيعية ومختلفة.
7) لا ترفض الوظيفة بسبب نقص المعلومات.
8) seo_title أولوية عالية: ابدأ باسم جهة التوظيف عندما يكون معروفاً، وأبرز أقوى ميزة مثبتة مثل تعدد التخصصات أو حديثي التخرج أو عدد الفرص إذا كان مثبتاً. يجوز استخدام الراتب التجميعي فقط إذا كان موسوماً صراحة بكلمة «متوقع» أو «تقديري». لا تستخدم Clickbait مضلل.
9) social_title أكثر جذباً قليلاً من seo_title مع الالتزام بنفس الحقائق ونفس وسم الراتب التقديري عند استخدامه.
10) meta_description قصيرة ومباشرة وتذكر أهم سبب للنقر وطريقة التقديم إن كانت مثبتة. إذا كان الإعلان نفسه يذكر راتباً متوقعاً/تقديرياً فيجوز إبقاؤه بنفس الوصف.
11) summary من 70 إلى 110 كلمة تقريباً، يشرح الفرصة بوضوح ولا يكرر الجداول حرفياً. يمكن أن يذكر الراتب المتوقع مع توضيح أنه تقديري وغير رسمي إذا لم يؤكده المصدر الأصلي.
12) reader_value أولوية عالية ويجب أن يحتوي قيمة عملية أصلية: who_might_fit نقطتان، what_makes_this_opportunity_notable نقطتان، application_checklist ثلاث نقاط. كلها إرشادات عامة وليست شروطاً رسمية.
13) official_requirements وofficial_duties لا تضف لهما إلا ما ورد فعلاً. إذا لم يوجد شيء اترك القائمة فارغة.
14) missing_official_information اجمع أهم المعلومات الناقصة فقط، بحد أقصى 6 عناصر.
15) general_guidance منخفض الأولوية: استخدم بحد أقصى نقطة واحدة في كل قسم فقط إذا بقيت مساحة، وإلا اترك القوائم فارغة. لا تكتب {MISSING} داخل قوائم الإرشادات.
16) faq منخفض الأولوية ويمكن تركه فارغاً؛ النظام سيولد أسئلة حقائق تلقائياً عند الحاجة. إن كتبته فبحد أقصى سؤالين قصيرين.
17) safety_note جملة واحدة قصيرة فقط.
18) labels بحد أقصى 5، وschema_supported_fields يحتوي فقط حقولاً مدعومة فعلاً.
19) اختصر الإجابة لتبقى ضمن حد 950 output tokens؛ لا تهدر التوكنز على تكرار المعلومات.
20) أخرج JSON فقط بدون Markdown أو شرح خارجي.
21) استخدم العربية الفصحى المبسطة المناسبة للأردن.
""".strip()

OUTPUT_SHAPE = {
    "seo_title": "", "social_title": "", "meta_description": "", "summary": "",
    "official_details": {"employer": MISSING, "job_title": MISSING, "location": MISSING, "salary": MISSING, "employment_type": MISSING, "experience": MISSING, "qualification": MISSING, "application_method": MISSING, "deadline": MISSING},
    "official_requirements": [], "official_duties": [], "missing_official_information": [],
    "reader_value": {"who_might_fit": [], "application_checklist": [], "what_makes_this_opportunity_notable": []},
    "general_guidance": {"skills_that_may_help": [], "cv_tips": [], "before_applying": []},
    "faq": [], "safety_note": "", "verification_notes": [], "labels": [], "schema_supported_fields": [],
}


def compact_source_text(value: str | None, limit: int) -> str | None:
    if not value: return None
    return re.sub(r"\n{3,}", "\n\n", value).strip()[:limit]


def prompt_for(job: dict) -> str:
    compact_job = {
        "title": job.get("title"), "page_title": job.get("page_title"), "source_name": job.get("source_name"),
        "source_discovery_url": job.get("source_discovery_url"), "source_original_url": job.get("source_original_url"),
        "source_original_fetch_ok": job.get("source_original_fetch_ok"), "application_email": job.get("application_email"),
        "application_phone": job.get("application_phone"), "application_url": job.get("application_url"),
        "dates_found": job.get("dates_found", [])[:8], "feed_published": job.get("feed_published"),
        "country": job.get("country", "Jordan"), "original_text": compact_source_text(job.get("original_text"), 9000),
        "discovery_text": compact_source_text(job.get("discovery_text"), 5000),
    }
    return json.dumps({"job": compact_job, "required_output_shape": OUTPUT_SHAPE}, ensure_ascii=False)


def extract_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S | re.I).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start: raise RuntimeError("Groq/Qwen output did not contain a JSON object")
    try: result = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc: raise RuntimeError(f"Invalid JSON from Groq/Qwen: {exc}") from exc
    if not isinstance(result, dict): raise RuntimeError("Groq/Qwen JSON root is not an object")
    return result


def retry_delay(response: requests.Response, attempt: int) -> float:
    header = response.headers.get("retry-after")
    if header:
        try: return max(2.0, min(float(header) + 2.0, 90.0))
        except ValueError: pass
    match = re.search(r"try again in\s+([0-9.]+)s", response.text or "", flags=re.I)
    if match:
        return max(2.0, min(float(match.group(1)) + 3.0, 90.0))
    return min(65.0, 20.0 * (attempt + 1))


def run_qwen(job: dict) -> dict:
    if not GROQ_API_KEY: raise RuntimeError("Missing GROQ_API_KEY secret")
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "system", "content": SYSTEM_RULES}, {"role": "user", "content": prompt_for(job)}],
        "temperature": TEMP, "max_completion_tokens": MAX_TOKENS, "reasoning_effort": "none",
        "response_format": {"type": "json_object"},
    }
    r = None
    for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
        r = requests.post(GROQ_URL, headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=120)
        if r.ok: break
        if r.status_code == 429 and attempt < MAX_RATE_LIMIT_RETRIES:
            delay = retry_delay(r, attempt)
            print(f"Groq free-plan rate limit reached; retrying in {delay:.1f}s (attempt {attempt + 1}/{MAX_RATE_LIMIT_RETRIES})", flush=True)
            time.sleep(delay)
            continue
        raise RuntimeError(f"Groq API failed HTTP {r.status_code}: {r.text[:1800]}")
    assert r is not None and r.ok
    data = r.json()
    result = extract_json(data["choices"][0]["message"]["content"])
    usage = data.get("usage") or {}
    result["ai_provider"] = "groq_free_plan"; result["ai_model"] = GROQ_MODEL
    result["paid_api_used"] = False; result["paid_fallback_used"] = False
    result["usage"] = {"prompt_tokens": usage.get("prompt_tokens"), "completion_tokens": usage.get("completion_tokens"), "total_tokens": usage.get("total_tokens")}
    return result


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(); parser.add_argument("input_json"); parser.add_argument("output_json"); args = parser.parse_args()
    job = json.loads(Path(args.input_json).read_text(encoding="utf-8")); result = run_qwen(job)
    out = Path(args.output_json); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"); print(out)
