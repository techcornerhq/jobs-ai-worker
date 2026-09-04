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


def detail(label: str, value, icon: str = "•") -> str:
    return (
        "<div class='job-fact'>"
        f"<span class='job-fact-icon'>{esc(icon)}</span>"
        f"<div><strong>{esc(label)}</strong><span>{esc(value or MISSING)}</span></div>"
        "</div>"
    )


def chip(label: str, value) -> str:
    value = str(value or "").strip()
    if not value or value == MISSING:
        return ""
    return f"<span class='job-top-chip'><b>{esc(label)}</b>{esc(value)}</span>"


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
  <section class='job-related-box job-panel'>
    <div class='job-section-heading'><span>↗</span><div><h2>وظائف مشابهة قد تهمك</h2><p>اكتشف فرصاً أحدث ضمن نفس المدينة أو المجال.</p></div></div>
    <div class='job-related-links'>{chips}<a class='job-related-chip' href='/search'>أحدث الوظائف</a></div>
  </section>
"""


def render(job: dict, enriched: dict) -> dict:
    official = enriched.get("official_details") or {}
    guidance = enriched.get("general_guidance") or {}
    reader_value = enriched.get("reader_value") or {}
    labels = classify_labels(job, enriched)
    title = enriched.get("seo_title") or job.get("job_title") or job.get("title") or "فرصة عمل جديدة"
    verified_at = job.get("verified_at") or job.get("date_discovered") or MISSING
    featured_image_url = str(job.get("featured_image_url") or "").strip()

    employer = official.get("employer") or MISSING
    job_title = official.get("job_title") or job.get("job_title") or title
    location = official.get("location") or MISSING
    employment_type = official.get("employment_type") or MISSING
    salary = official.get("salary") or MISSING
    deadline = official.get("deadline") or MISSING

    image_html = ""
    if featured_image_url:
        image_html = (
            "<figure class='job-featured-image'>"
            f"<img src='{esc(featured_image_url)}' alt='{esc(job_title)} لدى {esc(employer)}' loading='eager' fetchpriority='high' width='1536' height='1024'/>"
            "</figure>"
        )

    repost_note = ""
    if job.get("repost_of"):
        repost_note = "<div class='job-note'><strong>إعادة نشر حديثة</strong><span>ظهرت هذه الفرصة من جديد بعد حملة سابقة.</span></div>"

    verification_notes = clean_items(enriched.get("verification_notes"))
    verification_html = f"<ul>{li(verification_notes)}</ul>" if verification_notes else "<p>تم تنظيم المعلومات المتاحة مع فصل الحقائق المؤكدة عن الإرشادات العامة.</p>"

    faq_items = enriched.get("faq") or deterministic_faq(job, official)
    faqs = faq_html(faq_items)

    application_bits = [f"<p class='job-apply-method'>{esc(official.get('application_method'))}</p>"]
    if job.get("application_email"):
        email = esc(job.get("application_email"))
        application_bits.append(f"<p class='job-contact-row'><strong>البريد الإلكتروني</strong><a href='mailto:{email}'>{email}</a></p>")
    if job.get("application_phone"):
        application_bits.append(f"<p class='job-contact-row'><strong>الهاتف</strong><span>{esc(job.get('application_phone'))}</span></p>")
    if job.get("application_url"):
        application_bits.append(
            f"<a class='job-apply-btn' href='{esc(job.get('application_url'))}' rel='nofollow noopener' target='_blank'>التقديم على الوظيفة</a>"
        )
    application_html = "".join(application_bits)

    requirements = clean_items(enriched.get("official_requirements"))
    duties = clean_items(enriched.get("official_duties"))
    requirements_html = f"<ul class='job-list'>{li(requirements)}</ul>" if requirements else "<p>لم يذكر الإعلان شروطاً تفصيلية إضافية يمكن تأكيدها.</p>"
    duties_html = f"<ul class='job-list'>{li(duties)}</ul>" if duties else "<p>لم يذكر الإعلان مهاماً تفصيلية إضافية يمكن تأكيدها.</p>"

    guidance_sections: list[str] = []
    skills = clean_items(guidance.get("skills_that_may_help"))
    cv_tips = clean_items(guidance.get("cv_tips"))
    before = clean_items(guidance.get("before_applying"))
    if skills:
        guidance_sections.append(f"<h3>مهارات قد تساعدك</h3><ul class='job-list'>{li(skills)}</ul>")
    if cv_tips:
        guidance_sections.append(f"<h3>نصيحة للسيرة الذاتية</h3><ul class='job-list'>{li(cv_tips)}</ul>")
    if before:
        guidance_sections.append(f"<h3>قبل إرسال الطلب</h3><ul class='job-list'>{li(before)}</ul>")
    guidance_html = ""
    if guidance_sections:
        guidance_html = f"""
  <section class='job-guidance-box job-panel'>
    <span class='job-guidance-badge'>إرشادات للباحث عن عمل</span>
    <h2>نصائح تساعدك قبل التقديم</h2>
    <p class='job-muted'>{GUIDANCE_LABEL}</p>
    {''.join(guidance_sections)}
  </section>
"""

    quick_chips = "".join([
        chip("الموقع", location),
        chip("الدوام", employment_type),
        chip("الراتب", salary),
        chip("آخر موعد", deadline),
    ])

    who_fit = li(reader_value.get("who_might_fit"), "راجع التخصصات المطلوبة وقارنها بخبرتك أو مؤهلك قبل التقديم.")
    notable = li(reader_value.get("what_makes_this_opportunity_notable"), "راجع تفاصيل الإعلان وطريقة التقديم لتحديد مدى مناسبتها لك.")
    checklist = li(reader_value.get("application_checklist"), "جهز سيرة ذاتية محدثة وتأكد من بيانات التواصل قبل الإرسال.")

    summary = enriched.get("summary") or "تفاصيل الوظيفة مرتبة بشكل واضح مع فصل المعلومات الرسمية عن النصائح العامة."

    content = f"""
<article class='jordan-job-article'>
  <header class='job-page-hero'>
    <p class='job-kicker'>فرصة عمل في الأردن</p>
    <h1 class='job-display-title'>{esc(job_title)}</h1>
    <p class='job-employer'>{esc(employer)}</p>
    <div class='job-top-chips'>{quick_chips}</div>
    <a class='job-primary-cta' href='#job-apply'>عرض طريقة التقديم</a>
  </header>

  <div class='job-overview-grid'>
    {image_html}
    <div class='job-intro-card'>
      <span class='job-overview-label'>نظرة سريعة</span>
      <p>{esc(summary)}</p>
      <div class='job-verified-pill'>✓ معلومات منظمة ومراجعة قبل النشر</div>
    </div>
  </div>

  {repost_note}

  <section class='job-section' id='job-summary'>
    <div class='job-section-heading'><span>▦</span><div><h2>ملخص الوظيفة</h2><p>أهم المعلومات التي تحتاجها قبل قراءة التفاصيل.</p></div></div>
    <div class='job-facts-grid'>
      {detail('جهة التوظيف', employer, '◆')}
      {detail('الموقع', location, '⌖')}
      {detail('نوع الدوام', employment_type, '▣')}
      {detail('الراتب الرسمي', salary, '$')}
      {detail('الخبرة', official.get('experience'), '★')}
      {detail('المؤهل', official.get('qualification'), '✓')}
      {detail('آخر موعد', deadline, '◷')}
      {detail('المسمى الوظيفي', job_title, '▤')}
    </div>
  </section>

  <section class='job-value-box job-panel'>
    <span class='job-guidance-badge'>إرشادات للباحث عن عمل</span>
    <h2>هل هذه الفرصة مناسبة لك؟</h2>
    <p class='job-muted'>{GUIDANCE_LABEL}</p>
    <div class='job-value-columns'>
      <div><h3>قد تناسبك إذا</h3><ul class='job-check-list'>{who_fit}</ul></div>
      <div><h3>ما الذي يميزها؟</h3><ul class='job-check-list'>{notable}</ul></div>
    </div>
    <div class='job-checklist'><h3>قائمة تحقق سريعة قبل التقديم</h3><ul class='job-check-list'>{checklist}</ul></div>
  </section>

  <section class='job-section'>
    <div class='job-section-heading'><span>✓</span><div><h2>الشروط والمتطلبات المذكورة في الإعلان</h2><p>المعلومات الرسمية التي أمكن تأكيدها من الإعلان.</p></div></div>
    {requirements_html}
  </section>

  <section class='job-section'>
    <div class='job-section-heading'><span>▤</span><div><h2>المهام والمسؤوليات المذكورة</h2><p>المهام التي وردت في الإعلان عند توفرها.</p></div></div>
    {duties_html}
  </section>

  <section class='job-apply-section job-panel' id='job-apply'>
    <span class='job-apply-badge'>التقديم</span>
    <h2>طريقة التقديم</h2>
    {application_html}
  </section>

  <section class='job-section job-missing'>
    <div class='job-section-heading'><span>i</span><div><h2>معلومات لم يذكرها الإعلان بوضوح</h2><p>لا نملأ أي معلومات رسمية من عندنا.</p></div></div>
    <ul class='job-list'>{li(enriched.get('missing_official_information'), 'لا توجد معلومات ناقصة رئيسية مسجلة.')}</ul>
  </section>

  {guidance_html}

  {f"<section class='job-section job-faq-section'><div class='job-section-heading'><span>?</span><div><h2>أسئلة شائعة عن هذه الفرصة</h2><p>إجابات سريعة على أهم الأسئلة.</p></div></div>{faqs}</section>" if faqs else ""}

  {related_links_html(job, enriched)}

  <section class='job-safety-box job-panel'>
    <div class='job-section-heading'><span>!</span><div><h2>تنبيه مهم للباحثين عن عمل</h2><p>حافظ على بياناتك وتأكد من جهة التوظيف.</p></div></div>
    <p>{esc(enriched.get('safety_note') or 'تحقق من جهة التوظيف قبل مشاركة بيانات حساسة، ولا تدفع أي مبالغ مقابل الحصول على وظيفة.')}</p>
  </section>

  <section class='job-verification'>
    <h2>التحقق من الإعلان</h2>
    <p>تم رصد هذه الفرصة عبر مصدر وظائف خارجي، ثم تنظيم المعلومات والتحقق من وسيلة التقديم والمصدر الرسمي عندما يكون متاحاً. آخر تحقق مسجل: {esc(verified_at)}.</p>
    {verification_html}
  </section>
</article>

<style>
.jordan-job-article{{--j-primary:#0f766e;--j-text:#172033;--j-muted:#667085;--j-border:#e4e7ec;--j-soft:#f7f9fc;line-height:1.9;color:#344054}}
.job-page-hero{{padding:6px 0 22px;border-bottom:1px solid var(--j-border);margin-bottom:24px}}
.job-kicker{{font-size:13px;font-weight:800;color:var(--j-primary);margin:0 0 6px}}
.job-display-title{{font-size:36px!important;line-height:1.3!important;font-weight:900!important;color:var(--j-text)!important;margin:0 0 6px!important;letter-spacing:0!important}}
.job-employer{{font-size:17px;font-weight:700;color:#475467;margin:0 0 14px}}
.job-top-chips{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 16px}}
.job-top-chip{{display:inline-flex;align-items:center;gap:5px;min-height:36px;padding:0 11px;border:1px solid var(--j-border);border-radius:999px;background:#fff;font-size:13px;color:#475467}}.job-top-chip b{{color:var(--j-muted);font-weight:600}}
.job-primary-cta{{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:0 18px;border-radius:11px;background:#eaf7f5;color:var(--j-primary)!important;font-weight:900;text-decoration:none}}
.job-overview-grid{{display:grid;grid-template-columns:minmax(0,1.18fr) minmax(280px,.82fr);gap:18px;align-items:stretch;margin:0 0 26px}}
.job-featured-image{{margin:0;min-width:0}}.job-featured-image img{{display:block;width:100%;height:100%;min-height:300px;object-fit:cover;border-radius:16px;border:1px solid var(--j-border)}}
.job-intro-card{{padding:22px;border:1px solid var(--j-border);border-radius:16px;background:var(--j-soft);display:flex;flex-direction:column;justify-content:center}}.job-intro-card p{{font-size:16px;line-height:1.95;margin:7px 0 14px}}.job-overview-label{{font-size:13px;font-weight:800;color:var(--j-primary)}}.job-verified-pill{{display:inline-flex;align-items:center;align-self:flex-start;min-height:34px;padding:0 10px;border-radius:999px;background:#eaf7f5;color:var(--j-primary);font-size:12px;font-weight:800}}
.job-note{{display:flex;gap:8px;align-items:center;padding:12px 14px;border-radius:12px;background:#fff8e8;border:1px solid #f4ddb0;margin:0 0 22px;font-size:13px}}
.job-section{{margin:34px 0}}.job-section-heading{{display:flex;align-items:flex-start;gap:11px;margin-bottom:15px}}.job-section-heading>span{{flex:0 0 36px;width:36px;height:36px;display:grid;place-items:center;border-radius:10px;background:#eaf7f5;color:var(--j-primary);font-weight:900}}.job-section-heading h2{{font-size:25px!important;line-height:1.4!important;font-weight:900!important;color:var(--j-text)!important;margin:0!important}}.job-section-heading p{{font-size:13px;color:var(--j-muted);margin:3px 0 0}}
.job-facts-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.job-fact{{min-height:95px;padding:14px;border:1px solid var(--j-border);border-radius:13px;background:#fff;display:flex;align-items:flex-start;gap:10px}}.job-fact-icon{{width:30px;height:30px;flex:0 0 30px;display:grid;place-items:center;border-radius:9px;background:var(--j-soft);color:var(--j-primary);font-weight:900}}.job-fact strong,.job-fact div>span{{display:block}}.job-fact strong{{font-size:12px;color:var(--j-muted);margin-bottom:3px}}.job-fact div>span{{font-size:14px;font-weight:800;color:var(--j-text);line-height:1.6;overflow-wrap:anywhere}}
.job-panel{{padding:22px;border:1px solid var(--j-border);border-radius:16px;margin:28px 0;background:#fff}}.job-guidance-badge,.job-apply-badge{{display:inline-flex;min-height:30px;align-items:center;padding:0 9px;border-radius:999px;background:#eef8f6;color:var(--j-primary);font-size:12px;font-weight:900;margin-bottom:8px}}.job-muted{{font-size:13px;color:var(--j-muted)}}
.job-value-box{{background:#f8fbff;border-color:#d9e6f6}}.job-value-columns{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.job-value-box h2,.job-guidance-box h2{{font-size:24px!important;margin:0 0 6px!important}}.job-value-box h3,.job-guidance-box h3{{font-size:17px!important;margin:15px 0 7px!important}}.job-checklist{{margin-top:12px;padding-top:12px;border-top:1px solid #dce5ef}}
.job-list,.job-check-list{{padding-right:22px;margin:10px 0}}.job-list li,.job-check-list li{{margin:8px 0;line-height:1.8}}.job-check-list li::marker{{color:var(--j-primary)}}
.job-apply-section{{background:#f2fbf9;border-color:#bfe2dc;scroll-margin-top:90px}}.job-apply-section h2{{font-size:28px!important;color:var(--j-text)!important;margin:0 0 8px!important}}.job-apply-method{{font-size:16px;margin:0 0 14px}}.job-contact-row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:8px 0}}.job-contact-row strong{{color:var(--j-muted);font-size:13px}}.job-apply-btn{{display:inline-flex;align-items:center;justify-content:center;min-height:50px;padding:0 20px;margin-top:8px;border-radius:12px;background:var(--j-primary);color:#fff!important;text-decoration:none;font-size:15px;font-weight:900}}.job-apply-btn:hover{{filter:brightness(.94)}}
.job-guidance-box{{border-right:4px solid var(--j-primary);background:#fbfdfd}}.job-safety-box{{background:#fffaf0;border-color:#f4ddb0}}.job-safety-box .job-section-heading>span{{background:#fff0cf;color:#b76a00}}.job-related-box{{background:#f7fffd;border-color:#cce8e3}}.job-related-links{{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}}.job-related-chip{{display:inline-flex;align-items:center;min-height:38px;padding:0 12px;border-radius:999px;border:1px solid #b9e2dc;background:#fff;color:var(--j-primary)!important;text-decoration:none;font-weight:800;font-size:13px}}
.job-faq{{padding:0;border:1px solid var(--j-border);border-radius:12px;margin:9px 0;background:#fff;overflow:hidden}}.job-faq summary{{min-height:50px;display:flex;align-items:center;padding:12px 14px;font-size:15px;font-weight:800;cursor:pointer;color:var(--j-text);list-style:none}}.job-faq summary::-webkit-details-marker{{display:none}}.job-faq p{{padding:0 14px 14px;margin:0;color:#475467}}
.job-verification{{margin:34px 0 8px;padding-top:20px;border-top:1px solid var(--j-border);color:var(--j-muted);font-size:13px}}.job-verification h2{{font-size:19px!important;color:#475467!important;margin:0 0 8px!important}}.job-verification ul{{padding-right:20px}}
@media(max-width:900px){{.job-overview-grid{{grid-template-columns:1fr}}.job-facts-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.job-featured-image img{{min-height:0;height:auto}}}}
@media(max-width:640px){{.job-page-hero{{padding-top:0;margin-bottom:18px}}.job-display-title{{font-size:28px!important;line-height:1.4!important}}.job-employer{{font-size:15px}}.job-top-chips{{gap:6px}}.job-top-chip{{min-height:34px;font-size:12px;padding:0 9px}}.job-primary-cta{{width:100%;min-height:48px}}.job-overview-grid{{gap:12px;margin-bottom:22px}}.job-intro-card{{padding:16px}}.job-facts-grid{{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}}.job-fact{{min-height:104px;padding:11px;gap:7px;flex-direction:column}}.job-fact-icon{{width:28px;height:28px;flex-basis:28px}}.job-fact div>span{{font-size:13px}}.job-section{{margin:28px 0}}.job-section-heading h2{{font-size:21px!important}}.job-panel{{padding:16px;margin:24px 0}}.job-value-columns{{grid-template-columns:1fr;gap:5px}}.job-apply-section h2{{font-size:24px!important}}.job-related-links{{gap:6px}}.job-related-chip{{font-size:12px;min-height:36px;padding:0 10px}}}}
</style>
""".strip()

    supported = set(enriched.get("schema_supported_fields") or [])
    schema: dict = {"@context": "https://schema.org", "@type": "JobPosting"}
    schema_job_title = official.get("job_title")
    if "title" in supported and schema_job_title not in (None, "", MISSING):
        schema["title"] = schema_job_title
    if enriched.get("summary"):
        schema["description"] = enriched["summary"]
    if "datePosted" in supported and job.get("date_posted"):
        schema["datePosted"] = job["date_posted"]
    if "validThrough" in supported and job.get("valid_through"):
        schema["validThrough"] = job["valid_through"]
    schema_employer = official.get("employer")
    if "hiringOrganization" in supported and schema_employer not in (None, "", MISSING):
        schema["hiringOrganization"] = {"@type": "Organization", "name": schema_employer}
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
