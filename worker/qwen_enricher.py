from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

MODEL_PATH = os.getenv("QWEN_MODEL_PATH", "models/Qwen3-8B-Q4_K_M.gguf").strip()
LLAMA_CLI = os.getenv("LLAMA_CLI", "llama-cli")
MAX_TOKENS = int(os.getenv("QWEN_MAX_TOKENS", "1600"))
CTX = int(os.getenv("QWEN_CTX", "8192"))
TEMP = os.getenv("QWEN_TEMP", "0.20")

MISSING = "غير مذكور في الإعلان"

SYSTEM_RULES = f"""
أنت محرر وظائف عربي دقيق لموقع وظائف الأردن. المطلوب تحويل بيانات الإعلان الخام إلى JSON منظم ومفيد وقابل للنشر.

قواعد إلزامية لا يجوز مخالفتها:
1) لا تختلق أي حقيقة رسمية: اسم الشركة، الراتب، الموقع، الموعد النهائي، المؤهل، الخبرة، عدد الشواغر، ساعات العمل، المزايا أو طريقة التقديم.
2) إذا لم تجد معلومة مدعومة بالنص الرسمي/الأصلي فاكتب حرفياً: {MISSING}
3) المصدر التجميعي discovery source ليس مصدراً رسمياً بحد ذاته. إذا كتب "راتب متوقع" أو "تقديري" فلا تحوله إلى راتب رسمي إلا إذا أكده original_text أو مصدر أصلي واضح.
4) يجوز كتابة نصائح عامة مفيدة للمتقدم، لكن ضعها فقط داخل general_guidance، ولا تصفها أبداً كمتطلبات الشركة.
5) لا تنسخ فقرات المصدر حرفياً. أعد تنظيم الحقائق بصياغة عربية طبيعية ومختصرة مع قيمة تحريرية حقيقية.
6) إذا كانت المعلومات قليلة لا ترفض الوظيفة؛ أنشئ صفحة مفيدة من الحقائق المتاحة + المعلومات الناقصة + إرشادات عامة واضحة.
7) لا تقل إن الوظيفة "مضمونة" أو "مؤكدة". اذكر حدود التحقق عند الحاجة.
8) schema_supported_fields يجب أن يحتوي فقط أسماء الحقول التي توجد لها حقيقة مدعومة، مثل title, hiringOrganization, jobLocation, datePosted, validThrough.
9) labels بحد أقصى 5، قصيرة وملائمة للوظيفة (مثل عمان، مبيعات، دوام كامل، بدون خبرة، حكومي).
10) seo_title طبيعي وغير مضلل ولا يذكر راتباً غير رسمي.
11) meta_description من 120 إلى 160 حرفاً تقريباً، مفيدة وغير محشوة بالكلمات المفتاحية.
12) الناتج JSON فقط: يبدأ بـ {{ وينتهي بـ }}. ممنوع Markdown أو أي شرح خارج JSON.
13) استخدم العربية الفصحى المبسطة المناسبة للأردن.
14) إذا وجدت تعارضاً بين discovery_text و original_text ففضّل original_text واذكر التعارض في verification_notes.
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


def prompt_for(job: dict) -> str:
    compact_job = dict(job)
    # Keep enough source text for understanding while avoiding needless context bloat.
    for key in ("discovery_text", "original_text"):
        if compact_job.get(key):
            compact_job[key] = compact_job[key][:18000]
    payload = {"job": compact_job, "required_output_shape": OUTPUT_SHAPE}
    return SYSTEM_RULES + "\n\nINPUT_JSON:\n" + json.dumps(payload, ensure_ascii=False)


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
            "--no-display-prompt",
        ]
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=3600)
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
