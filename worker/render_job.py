from __future__ import annotations

import html
import json

from taxonomy import category_links, classify_labels

MISSING = "غير مذكور في الإعلان"
GUIDANCE_LABEL = "معلومات إرشادية عامة وليست شرطاً معلناً من جهة التوظيف"


def esc(value) -> str:
    return html.escape(str(value or MISSING), quote=True)


def clean_items(items) -> list[str]:
    out: list[str] = []
    for x in items or []:
        value = str(x or "").strip()
        if value and value != MISSING:
            out.append(value)
    return out


def li(items, fallback: str | None = None) -> str:
    items = clean_items(items)
    if not items:
        return f"<li>{esc(fallback or MISSING)}</li>"
    return "".join(f"<li>{esc(x)}</li>" for x in items)


def detail(label: str, value) -> str:
    return f"<div class='job-fact'><strong>{esc(label)}</strong><span>{esc(value or MISSING)}</span></div>"


def faq_html(items) -> str:
    out: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("question") or "").strip()
        a = str(item.get("answer") or "").strip()
        if q and a:
            out.append(f"<details class='job-faq'><summary>{esc(q)}</summary><p>{esc(a)}</p></details>")
    return "".join(out)


def deterministic_faq(job: dict, official: dict) -> list[dict]:
    method = official.get("application_method") or MISSING
    salary = official.get("salary") or MISSING
    location = official.get("location") or MISSING
    deadline = official.get("deadline") or MISSING
    email = str(job.get("application_email") or "").strip()
    apply_answer = method
    if email:
        apply_answer = f"{method}. البريد الإلكتروني المخصص للتقديم: {email}."
    return [
        {"question": "كيف يمكن التقديم على هذه الفرصة؟", "answer": apply_answer},
        {"question": "هل الراتب مذكور في الإعلان؟", "answer": salary if salary != MISSING else "لا، الراتب الرسمي غير مذكور في الإعلان المتاح لدينا."},
        {"question": "أين مكان العمل وما آخر موعد للتقديم؟", "answer": f"مكان العمل: {location}. آخر موعد: {deadline}."},
    ]


def related_links_html(job: dict, enriched: dict) -> str:
    links = category_links(job, enriched)
    chips = "".join(
        f"<a class='job-related-chip' href='{esc(url)}'>{esc(label)}</a>" for label, url in links
    )
    return f"""
  <div class='job-related-box'>
    <h2>وظائف مشابهة قد تهمك</h2>
    <p>تصفح فرصاً أحدث ضمن نفس المدينة أو المجال بدل الاعتماد على إعلان واحد فقط.</p>
    <div class='job-related-links'>{chips}<a class='job-related-chip' href='/search'>أحدث الوظائف</a></div>
  </div>
"""


def render(job: dict, enriched: dict) -> dict:
    official = enriched.get("official_details") or {}
    guidance = enriched.get("general_guidance") or {}
    reader_value = enriched.get("reader_value") or {}
    labels = classify_labels(job, enriched)
    title = enriched.get("seo_title") or job.get("job_title") or job.get("title") or "فرصة عمل جديدة"
    verified_at = job.get("verified_at") or job.get("date_discovered") or MISSING
    featured_image_url = str(job.get("featured_image_url") or "").strip()

    image_html = ""
    if featured_image_url:
        image_html = f"<figure class='job-featured-image'><img src='{esc(featured_image_url)}' alt='{esc(title)}' loading='eager' fetchpriority='high'/></figure>"

    repost_note = ""
    if job.get("repost_of"):
        repost_note = "<div class='job-note'><strong>إعادة نشر:</strong> ظهرت هذه الفرصة من جديد بعد حملة سابقة، لذلك عوملت كإعادة نشر حديثة وليست نسخة مكررة من نفس اليوم.</div>"

    verification_notes = clean_items(enriched.get("verification_notes"))
    verification_html = f"<ul>{li(verification_notes)}</ul>" if verification_notes else "<p>تم تنظيم المعلومات المتاحة مع فصل الحقائق المؤكدة عن الإرشادات العامة.</p>"

    faq_items = enriched.get("faq") or deterministic_faq(job, official)
    faqs = faq_html(faq_items)

    application_bits = [f"<p>{esc(official.get('application_method'))}</p>"]
    if job.get("application_email"):
        email = esc(job.get("application_email"))
        application_bits.append(f"<p><strong>البريد الإلكتروني:</strong> <a href='mailto:{email}'>{email}</a></p>")
    if job.get("application_phone"):
        application_bits.append(f"<p><strong>الهاتف:</strong> {esc(job.get('application_phone'))}</p>")
    if job.get("application_url"):
        application_bits.append(f"<p><a class='job-apply-btn' href='{esc(job.get('application_url'))}' rel='nofollow noopener' target='_blank'>الانتقال إلى صفحة التقديم الرسمية</a></p>")
    application_html = "".join(application_bits)

    requirements = clean_items(enriched.get("official_requirements"))
    duties = clean_items(enriched.get("official_duties"))
    requirements_html = f"<ul>{li(requirements)}</ul>" if requirements else "<p>لم يذكر الإعلان شروطاً تفصيلية إضافية يمكن تأكيدها.</p>"
    duties_html = f"<ul>{li(duties)}</ul>" if duties else "<p>لم يذكر الإعلان مهاماً تفصيلية إضافية يمكن تأكيدها.</p>"

    guidance_sections: list[str] = []
    skills = clean_items(guidance.get("skills_that_may_help"))
    cv_tips = clean_items(guidance.get("cv_tips"))
    before = clean_items(guidance.get("before_applying"))
    if skills:
        guidance_sections.append(f"<h3>مهارات قد تكون مفيدة لهذا النوع من الوظائف</h3><ul>{li(skills)}</ul>")
    if cv_tips:
        guidance_sections.append(f"<h3>نصيحة للسيرة الذاتية</h3><ul>{li(cv_tips)}</ul>")
    if before:
        guidance_sections.append(f"<h3>قبل إرسال الطلب</h3><ul>{li(before)}</ul>")
    guidance_html = ""
    if guidance_sections:
        guidance_html = f"<div class='job-guidance-box'><h2>نصائح تساعدك قبل التقديم</h2><p><strong>{GUIDANCE_LABEL}</strong></p>{''.join(guidance_sections)}</div>"

    content = f"""
<article class='jordan-job-article'>
  {image_html}

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

  <div class='job-value-box'>
    <h2>هل هذه الفرصة مناسبة لك؟</h2>
    <p><strong>{GUIDANCE_LABEL}</strong></p>
    <ul>{li(reader_value.get('who_might_fit'), 'راجع التخصصات المطلوبة وقارنها بخبرتك أو مؤهلك قبل التقديم.')}</ul>
    <h3>ما الذي يميز هذه الفرصة؟</h3>
    <ul>{li(reader_value.get('what_makes_this_opportunity_notable'), 'راجع تفاصيل الإعلان وطريقة التقديم لتحديد مدى مناسبتها لك.')}</ul>
    <h3>قائمة تحقق سريعة قبل التقديم</h3>
    <ul>{li(reader_value.get('application_checklist'), 'جهز سيرة ذاتية محدثة وتأكد من بيانات التواصل قبل الإرسال.')}</ul>
  </div>

  <h2>الشروط والمتطلبات المذكورة في الإعلان</h2>
  {requirements_html}

  <h2>المهام والمسؤوليات المذكورة</h2>
  {duties_html}

  <h2>طريقة التقديم</h2>
  {application_html}

  <h2>معلومات لم يذكرها الإعلان بوضوح</h2>
  <ul>{li(enriched.get('missing_official_information'), 'لا توجد معلومات ناقصة رئيسية مسجلة.')}</ul>

  {guidance_html}

  {f"<h2>أسئلة شائعة عن هذه الفرصة</h2>{faqs}" if faqs else ""}

  {related_links_html(job, enriched)}

  <div class='job-safety-box'>
    <h2>تنبيه مهم للباحثين عن عمل</h2>
    <p>{esc(enriched.get('safety_note') or 'تحقق من جهة التوظيف قبل مشاركة بيانات حساسة، ولا تدفع أي مبالغ مقابل الحصول على وظيفة.')}</p>
  </div>

  <h2>التحقق من الإعلان</h2>
  <p>تم رصد هذه الفرصة عبر مصدر وظائف خارجي، ثم تنظيم المعلومات والتحقق من وسيلة التقديم والمصدر الرسمي عندما يكون متاحاً. آخر تحقق مسجل: {esc(verified_at)}.</p>
  {verification_html}
</article>

<style>
.jordan-job-article{{line-height:2}}
.job-featured-image{{margin:0 0 20px}}
.job-featured-image img{{display:block;width:100%;height:auto;border-radius:18px;border:1px solid #e5eaf0}}
.job-intro-card,.job-note,.job-value-box,.job-guidance-box,.job-safety-box,.job-related-box{{padding:18px;border:1px solid #e5eaf0;border-radius:16px;margin:18px 0;background:#f8fafc}}
.job-kicker{{font-size:12px;font-weight:800;color:#0f766e;margin:0 0 4px}}
.job-facts-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:16px 0 24px}}
.job-fact{{padding:13px 14px;border:1px solid #e5eaf0;border-radius:12px;background:#fff}}
.job-fact strong,.job-fact span{{display:block}}
.job-fact strong{{font-size:12px;color:#667085;margin-bottom:4px}}
.job-fact span{{font-weight:700;color:#172033}}
.job-value-box{{border-right:4px solid #2563eb;background:#f8fbff}}
.job-guidance-box{{border-right:4px solid #0f766e}}
.job-safety-box{{border-right:4px solid #f59e0b;background:#fffaf0}}
.job-related-box{{border-right:4px solid #0f766e;background:#f7fffd}}
.job-related-links{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}
.job-related-chip{{display:inline-block;padding:7px 11px;border-radius:999px;border:1px solid #b9e2dc;background:#fff;color:#0f766e!important;text-decoration:none;font-weight:700;font-size:13px}}
.job-faq{{padding:12px 14px;border:1px solid #e5eaf0;border-radius:12px;margin:10px 0;background:#fff}}
.job-faq summary{{font-weight:800;cursor:pointer;color:#172033}}
.job-faq p{{margin:8px 0 0}}
.job-apply-btn{{display:inline-block;padding:10px 16px;border-radius:10px;background:#0f766e;color:#fff!important;text-decoration:none;font-weight:800}}
@media(max-width:640px){{.job-facts-grid{{grid-template-columns:1fr}}.job-intro-card,.job-note,.job-value-box,.job-guidance-box,.job-safety-box,.job-related-box{{padding:15px}}}}
</style>
""".strip()

    supported = set(enriched.get("schema_supported_fields") or [])
    schema: dict = {"@context": "https://schema.org", "@type": "JobPosting"}
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
    if "jobLocation" in supported and (job.get("city") or job.get("governorate") or job.get("location_text")):
        schema["jobLocation"] = {
            "@type": "Place",
            "address": {
                "@type": "PostalAddress",
                "addressCountry": "JO",
                "addressRegion": job.get("governorate"),
                "addressLocality": job.get("city") or job.get("location_text"),
            },
        }

    if "title" not in schema:
        schema = {}
    else:
        content += "\n<script type='application/ld+json'>" + json.dumps(schema, ensure_ascii=False) + "</script>"

    return {
        "title": title,
        "social_title": enriched.get("social_title") or title,
        "labels": labels,
        "content": content,
        "schema": schema,
        "meta_description": enriched.get("meta_description"),
        "featured_image_url": featured_image_url or None,
    }
