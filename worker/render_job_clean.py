from __future__ import annotations

import html
from taxonomy import category_links, classify_labels

MISSING = "غير مذكور في الإعلان"


def esc(value) -> str:
    return html.escape(str(value or MISSING), quote=True)


def clean_items(items) -> list[str]:
    out=[]
    for x in items or []:
        v=str(x or '').strip()
        if v and v != MISSING:
            out.append(v)
    return out


def list_html(items, fallback: str) -> str:
    vals=clean_items(items)
    if not vals:
        vals=[fallback]
    return "<ul class='job-list'>"+''.join(f"<li>{esc(v)}</li>" for v in vals)+"</ul>"


def fact(label: str, value) -> str:
    return f"<div class='job-fact'><div><strong>{esc(label)}</strong><span>{esc(value or MISSING)}</span></div></div>"


def chip(label: str, value) -> str:
    v=str(value or '').strip()
    if not v or v == MISSING:
        return ''
    return f"<span class='job-top-chip'><b>{esc(label)}</b>{esc(v)}</span>"


def faq_html(items, official: dict, job: dict) -> str:
    faq=[]
    for item in items or []:
        if isinstance(item,dict):
            q=str(item.get('question') or '').strip(); a=str(item.get('answer') or '').strip()
            if q and a: faq.append((q,a))
    if not faq:
        faq=[
            ('كيف يمكن التقديم على هذه الوظيفة؟', str(official.get('application_method') or MISSING)),
            ('هل الراتب مذكور رسميًا؟', str(official.get('salary') or MISSING)),
            ('ما آخر موعد للتقديم؟', str(official.get('deadline') or MISSING)),
        ]
    return ''.join(f"<details class='job-faq'><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q,a in faq)


def related_links_html(job: dict, enriched: dict) -> str:
    links=category_links(job,enriched)
    anchors=''.join(f"<a class='job-related-chip' href='{esc(url)}'>{esc(label)}</a>" for label,url in links)
    return f"""<section class='job-related-box job-panel'><div class='job-section-heading'><div><h2>وظائف مشابهة قد تهمك</h2><p>تصفح فرصاً أخرى ضمن نفس المدينة أو المجال.</p></div></div><div class='job-related-links'>{anchors}<a class='job-related-chip' href='/search'>أحدث الوظائف</a></div></section>"""


def render(job: dict, enriched: dict) -> dict:
    official=enriched.get('official_details') or {}
    labels=classify_labels(job,enriched)
    title=enriched.get('seo_title') or job.get('job_title') or job.get('title') or 'فرصة عمل جديدة'
    employer=official.get('employer') or job.get('employer_name') or MISSING
    job_title=official.get('job_title') or job.get('job_title') or title
    location=official.get('location') or job.get('location_text') or MISSING
    employment_type=official.get('employment_type') or MISSING
    salary=official.get('salary') or MISSING
    experience=official.get('experience') or MISSING
    qualification=official.get('qualification') or MISSING
    deadline=official.get('deadline') or MISSING
    method=official.get('application_method') or job.get('application_method') or MISSING
    summary=enriched.get('summary') or 'تفاصيل الوظيفة مرتبة بشكل واضح مع توضيح المعلومات الرسمية وطريقة التقديم.'
    verified_at=job.get('verified_at') or job.get('date_discovered') or MISSING
    image_url=str(job.get('featured_image_url') or '').strip()

    top=''.join([chip('الموقع',location),chip('الدوام',employment_type),chip('آخر موعد',deadline)])
    image_html=f"<figure class='job-featured-image'><img src='{esc(image_url)}' alt='{esc(job_title)} لدى {esc(employer)}' loading='eager' fetchpriority='high' width='1536' height='1024'/></figure>" if image_url else ''

    apply=[]
    if method: apply.append(f"<p class='job-apply-method'>{esc(method)}</p>")
    if job.get('application_email'):
        e=esc(job['application_email']); apply.append(f"<p class='job-contact-row'><strong>البريد الإلكتروني</strong><a href='mailto:{e}'>{e}</a></p>")
    if job.get('application_phone'):
        apply.append(f"<p class='job-contact-row'><strong>الهاتف</strong><span>{esc(job['application_phone'])}</span></p>")
    if job.get('application_url'):
        apply.append(f"<a class='job-apply-btn' href='{esc(job['application_url'])}' rel='nofollow noopener' target='_blank'>الانتقال إلى صفحة التقديم</a>")
    if not job.get('application_url') and not job.get('application_email') and not job.get('application_phone'):
        apply.append("<p>وسيلة التقديم الرسمية غير متاحة بوضوح في البيانات الحالية، لذلك ننصح بمراجعة جهة التوظيف مباشرة.</p>")

    requirements=list_html(enriched.get('official_requirements'),'لم يذكر الإعلان شروطاً تفصيلية إضافية يمكن تأكيدها.')
    duties=list_html(enriched.get('official_duties'),'لم يذكر الإعلان مهاماً تفصيلية إضافية يمكن تأكيدها.')
    missing=list_html(enriched.get('missing_official_information'),'لا توجد معلومات ناقصة رئيسية مسجلة.')
    faqs=faq_html(enriched.get('faq'),official,job)
    verification=clean_items(enriched.get('verification_notes'))
    verification_html=list_html(verification,'تم تنظيم المعلومات المتاحة مع فصل الحقائق المؤكدة عن أي إرشادات عامة.')

    content=f"""
<article class='jordan-job-article'>
  <header class='job-page-hero'>
    <p class='job-kicker'>فرصة عمل في الأردن</p>
    <h1 class='job-display-title'>{esc(job_title)}</h1>
    <p class='job-employer'>{esc(employer)}</p>
    <div class='job-top-chips'>{top}</div>
    <a class='job-primary-cta' href='#job-apply'>طريقة التقديم</a>
  </header>

  {image_html}

  <section class='job-intro-card'>
    <span class='job-overview-label'>ملخص سريع</span>
    <p>{esc(summary)}</p>
  </section>

  <section class='job-section' id='job-summary'>
    <div class='job-section-heading'><div><h2>ملخص الوظيفة</h2><p>أهم التفاصيل الرسمية في مكان واحد.</p></div></div>
    <div class='job-facts-grid'>
      {fact('جهة التوظيف',employer)}
      {fact('الموقع',location)}
      {fact('نوع الدوام',employment_type)}
      {fact('الراتب الرسمي',salary)}
      {fact('الخبرة',experience)}
      {fact('المؤهل',qualification)}
      {fact('آخر موعد',deadline)}
      {fact('المسمى الوظيفي',job_title)}
    </div>
  </section>

  <section class='job-section'>
    <div class='job-section-heading'><div><h2>الشروط والمتطلبات المذكورة في الإعلان</h2><p>فقط الشروط التي أمكن استخلاصها من الإعلان.</p></div></div>
    {requirements}
  </section>

  <section class='job-section'>
    <div class='job-section-heading'><div><h2>المهام والمسؤوليات المذكورة</h2><p>المهام المعلنة عند توفرها.</p></div></div>
    {duties}
  </section>

  <section class='job-apply-section job-panel' id='job-apply'>
    <span class='job-apply-badge'>التقديم</span>
    <h2>طريقة التقديم</h2>
    {''.join(apply)}
  </section>

  <details class='job-faq job-more-info'><summary>معلومات لم يذكرها الإعلان بوضوح</summary><div class='job-more-info-body'>{missing}</div></details>

  <section class='job-section job-faq-section'>
    <div class='job-section-heading'><div><h2>أسئلة شائعة عن هذه الفرصة</h2><p>إجابات سريعة قبل التقديم.</p></div></div>
    {faqs}
  </section>

  {related_links_html(job,enriched)}

  <section class='job-safety-box job-panel'>
    <div class='job-section-heading'><div><h2>تنبيه مهم للباحثين عن عمل</h2><p>احمِ بياناتك قبل إرسال أي مستندات.</p></div></div>
    <p>{esc(enriched.get('safety_note') or 'تحقق من جهة التوظيف قبل مشاركة بيانات حساسة، ولا تدفع أي مبالغ مقابل الحصول على وظيفة.')}</p>
  </section>

  <section class='job-verification'>
    <h2>التحقق من الإعلان</h2>
    <p>تم رصد هذه الفرصة عبر مصدر وظائف خارجي، ثم تنظيم المعلومات والتحقق من وسيلة التقديم والمصدر الرسمي عندما يكون متاحاً. آخر تحقق مسجل: {esc(verified_at)}.</p>
    {verification_html}
  </section>
</article>

<style>
.jordan-job-article{{--j-primary:#0f766e;--j-text:#182230;--j-muted:#667085;--j-border:#e5e7eb;line-height:1.9;color:#344054}}
.job-page-hero{{padding:0 0 22px;border-bottom:1px solid var(--j-border);margin-bottom:22px}}.job-kicker{{font-size:12px;font-weight:800;color:var(--j-primary);margin:0 0 5px}}.job-display-title{{font-size:34px!important;line-height:1.35!important;font-weight:900!important;color:var(--j-text)!important;margin:0 0 5px!important}}.job-employer{{font-size:16px;font-weight:700;color:#475467;margin:0 0 13px}}.job-top-chips{{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:14px}}.job-top-chip{{display:inline-flex;align-items:center;gap:5px;min-height:34px;padding:0 10px;border:1px solid var(--j-border);border-radius:999px;background:#fff;font-size:12px;color:#475467}}.job-top-chip b{{color:var(--j-muted);font-weight:600}}.job-primary-cta{{display:inline-flex;min-height:44px;align-items:center;justify-content:center;padding:0 16px;border-radius:9px;background:var(--j-primary);color:#fff!important;font-weight:900}}
.job-featured-image{{margin:0 0 16px}}.job-featured-image img{{display:block;width:100%;height:auto;border:1px solid var(--j-border);border-radius:12px}}.job-intro-card{{padding:18px;border:1px solid var(--j-border);border-radius:12px;background:#fff;margin-bottom:28px}}.job-intro-card p{{margin:5px 0 0;font-size:16px;line-height:1.9}}.job-overview-label{{font-size:12px;font-weight:800;color:var(--j-primary)}}
.job-section{{margin:32px 0}}.job-section-heading{{margin-bottom:14px}}.job-section-heading h2{{font-size:23px!important;line-height:1.4!important;font-weight:900!important;color:var(--j-text)!important;margin:0!important}}.job-section-heading p{{font-size:13px;color:var(--j-muted);margin:4px 0 0}}.job-facts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}.job-fact{{padding:12px 13px;border:1px solid var(--j-border);border-radius:10px;background:#fff}}.job-fact strong,.job-fact span{{display:block}}.job-fact strong{{font-size:12px;color:var(--j-muted);margin-bottom:3px}}.job-fact span{{font-size:14px;font-weight:800;color:var(--j-text);line-height:1.6;overflow-wrap:anywhere}}.job-list{{padding-right:21px;margin:8px 0}}.job-list li{{margin:7px 0;line-height:1.85}}
.job-panel{{padding:18px;border:1px solid var(--j-border);border-radius:12px;margin:28px 0;background:#fff}}.job-apply-section{{background:#f1faf8;border-color:#bfe2dc;scroll-margin-top:90px}}.job-apply-badge{{display:inline-flex;align-items:center;min-height:28px;padding:0 8px;border-radius:999px;background:#dff4ef;color:var(--j-primary);font-size:11px;font-weight:900}}.job-apply-section h2{{font-size:25px!important;margin:7px 0 5px!important}}.job-apply-method{{margin:0 0 12px}}.job-contact-row{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:7px 0}}.job-apply-btn{{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 18px;margin-top:8px;border-radius:10px;background:var(--j-primary);color:#fff!important;font-size:14px;font-weight:900}}
.job-faq{{padding:0;border:1px solid var(--j-border);border-radius:10px;margin:8px 0;background:#fff;overflow:hidden}}.job-faq summary{{min-height:48px;display:flex;align-items:center;padding:11px 13px;font-size:14px;font-weight:800;cursor:pointer;color:var(--j-text)}}.job-faq p{{padding:0 13px 13px;margin:0;font-size:14px}}.job-more-info{{margin:28px 0}}.job-more-info-body{{padding:0 13px 10px}}.job-related-box{{background:#fff}}.job-related-links{{display:flex;gap:7px;flex-wrap:wrap}}.job-related-chip{{display:inline-flex;align-items:center;min-height:36px;padding:0 10px;border:1px solid var(--j-border);border-radius:999px;background:#fff;color:var(--j-primary)!important;font-size:12px;font-weight:800}}.job-safety-box{{background:#fff8e7;border-color:#f1dfb9}}.job-verification{{margin:28px 0 0;padding-top:18px;border-top:1px solid var(--j-border);color:#98a2b3;font-size:12px}}.job-verification h2{{font-size:16px!important;color:#667085!important;margin:0 0 6px!important}}
@media(max-width:640px){{.job-display-title{{font-size:26px!important}}.job-primary-cta{{width:100%;min-height:46px}}.job-intro-card{{padding:15px}}.job-intro-card p{{font-size:15px}}.job-facts-grid{{grid-template-columns:1fr}}.job-section{{margin:26px 0}}.job-section-heading h2{{font-size:20px!important}}.job-panel{{padding:15px;margin:22px 0}}.job-apply-section h2{{font-size:22px!important}}.job-apply-btn{{width:100%}}}}
</style>
""".strip()

    return {
        'title': title,
        'social_title': enriched.get('social_title') or title,
        'labels': labels,
        'content': content,
        'schema': {},
        'meta_description': enriched.get('meta_description'),
        'featured_image_url': image_url or None,
    }
