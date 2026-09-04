from __future__ import annotations

import html
import json
from pathlib import Path

MISSING = "غير مذكور في الإعلان"
GUIDANCE_LABEL = "معلومات إرشادية عامة وليست شرطاً معلناً من جهة التوظيف"


def esc(value) -> str:
    return html.escape(str(value or MISSING), quote=True)


def li(items) -> str:
    items = [x for x in (items or []) if str(x).strip()]
    if not items:
        return f"<li>{MISSING}</li>"
    return "".join(f"<li>{esc(x)}</li>" for x in items)


def detail(label: str, value) -> str:
    return f"<div class='job-fact'><strong>{esc(label)}</strong><span>{esc(value or MISSING)}</span></div>"


def render(job: dict, enriched: dict) -> dict:
    official = enriched.get("official_details") or {}
    guidance = enriched.get("general_guidance") or {}
    labels = [str(x).strip() for x in enriched.get("labels", []) if str(x).strip()][:5]
    title = enriched.get("seo_title") or job.get("job_title") or job.get("title") or "فرصة عمل جديدة"
    source_url = job.get("source_original_url") or job.get("source_discovery_url")
    source_name = job.get("source_name") or "المصدر"
    verified_at = job.get("verified_at") or job.get("date_discovered") or MISSING

    repost_note = ""
    if job.get("repost_of"):
        repost_note = "<div class='job-note'><strong>إعادة نشر:</strong> ظهرت هذه الفرصة من جديد بعد حملة سابقة، لذلك عوملت كإعادة نشر حديثة وليست نسخة مكررة من نفس اليوم.</div>"

    verification_notes = enriched.get("verification_notes") or []
    verification_html = f"<ul>{li(verification_notes)}</ul>" if verification_notes else "<p>تم تنظيم المعلومات المتاحة مع فصل الحقائق الرسمية عن الإرشادات العامة.</p>"

    content = f"""
<article class='jordan-job-article'>
  <div class='job-intro-card'>
    <p class='job-kicker'>فرصة عمل في الأردن</p>
    <p>{esc(enriched.get('summary') or 'تفاصيل الوظيفة مرتبة بشكل واضح مع فصل المعلومات الرسمية عن النصائح العامة.')}</p>
  </div>

  {repost_note}

  <h2>ملخص الوظيفة</h2>
  <div class='job-facts-grid'>
    {detail('جهة التوظيف', official.get('employer'))}
    {detail('المسمى الوظيفي', official.get('job_title'))}
    {detail('الموقع', official.get('location'))}
    {detail('نوع الدوام', official.get('employment_type'))}
    {detail('الراتب الرسمي', official.get('salary'))}
    {detail('الخبرة', official.get('experience'))}
    {detail('المؤهل', official.get('qualification'))}
    {detail('آخر موعد', official.get('deadline'))}
  </div>

  <h2>الشروط والمتطلبات المذكورة في الإعلان</h2>
  <ul>{li(enriched.get('official_requirements'))}</ul>

  <h2>المهام والمسؤوليات المذكورة</h2>
  <ul>{li(enriched.get('official_duties'))}</ul>

  <h2>طريقة التقديم</h2>
  <p>{esc(official.get('application_method'))}</p>

  <h2>معلومات لم يذكرها الإعلان بوضوح</h2>
  <ul>{li(enriched.get('missing_official_information'))}</ul>

  <div class='job-guidance-box'>
    <h2>نصائح تساعدك قبل التقديم</h2>
    <p><strong>{GUIDANCE_LABEL}</strong></p>
    <h3>مهارات قد تكون مفيدة لهذا النوع من الوظائف</h3>
    <ul>{li(guidance.get('skills_that_may_help'))}</ul>
    <h3>نصائح للسيرة الذاتية</h3>
    <ul>{li(guidance.get('cv_tips'))}</ul>
    <h3>قبل إرسال الطلب</h3>
    <ul>{li(guidance.get('before_applying'))}</ul>
  </div>

  <div class='job-safety-box'>
    <h2>تنبيه مهم للباحثين عن عمل</h2>
    <p>{esc(enriched.get('safety_note') or 'تحقق من جهة التوظيف قبل مشاركة بيانات حساسة، ولا تدفع أي مبالغ مقابل الحصول على وظيفة.')}</p>
  </div>

  <h2>المصدر والتحقق</h2>
  <p>تم العثور على الفرصة عبر <strong>{esc(source_name)}</strong>، وآخر تحقق مسجل لدينا: {esc(verified_at)}.</p>
  {verification_html}
  <p><a href='{esc(source_url)}' rel='nofollow noopener' target='_blank'>عرض مصدر الإعلان</a></p>
</article>

<style>
.jordan-job-article{{line-height:2}}
.job-intro-card,.job-note,.job-guidance-box,.job-safety-box{{padding:18px;border:1px solid #e5eaf0;border-radius:16px;margin:18px 0;background:#f8fafc}}
.job-kicker{{font-size:12px;font-weight:800;color:#0f766e;margin:0 0 4px}}
.job-facts-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:16px 0 24px}}
.job-fact{{padding:13px 14px;border:1px solid #e5eaf0;border-radius:12px;background:#fff}}
.job-fact strong,.job-fact span{{display:block}}
.job-fact strong{{font-size:12px;color:#667085;margin-bottom:4px}}
.job-fact span{{font-weight:700;color:#172033}}
.job-guidance-box{{border-right:4px solid #0f766e}}
.job-safety-box{{border-right:4px solid #f59e0b;background:#fffaf0}}
@media(max-width:640px){{.job-facts-grid{{grid-template-columns:1fr}}}}
</style>
""".strip()

    supported = set(enriched.get("schema_supported_fields") or [])
    schema = {"@context": "https://schema.org", "@type": "JobPosting"}
    job_title = official.get("job_title")
    if "title" in supported and job_title not in (None, "", MISSING):
        schema["title"] = job_title
    if enriched.get("summary"):
        schema["description"] = enriched["summary"]
    if "datePosted" in supported and job.get("date_posted"):
        schema["datePosted"] = job["date_posted"]
    if "validThrough" in supported and job.get("valid_through"):
        schema["validThrough"] = job["valid_through"]
    employer = official.get("employer")
    if "hiringOrganization" in supported and employer not in (None, "", MISSING):
        schema["hiringOrganization"] = {"@type": "Organization", "name": employer}
    if "jobLocation" in supported and (job.get("country") or job.get("city") or job.get("governorate") or job.get("location_text")):
        schema["jobLocation"] = {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "JO",
                "addressRegion": job.get("governorate"),
                "addressLocality": job.get("city") or job.get("location_text"),
            },
        }

    # Do not emit JobPosting structured data unless a supported title exists.
    if "title" not in schema:
        schema = {}
    else:
        content += "\n<script type='application/ld+json'>" + json.dumps(schema, ensure_ascii=False) + "</script>"

    return {
        "title": title,
        "labels": labels,
        "content": content,
        "schema": schema,
        "meta_description": enriched.get("meta_description"),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("job_json")
    parser.add_argument("enriched_json")
    parser.add_argument("output_json")
    args = parser.parse_args()
    job = json.loads(Path(args.job_json).read_text(encoding="utf-8"))
    enriched = json.loads(Path(args.enriched_json).read_text(encoding="utf-8"))
    result = render(job, enriched)
    path = Path(args.output_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(path)
