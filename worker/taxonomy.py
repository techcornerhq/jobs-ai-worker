from __future__ import annotations

import re
from urllib.parse import quote


def _text(*values) -> str:
    return " ".join(str(v or "") for v in values).lower()


def classify_labels(job: dict, enriched: dict | None = None) -> list[str]:
    enriched = enriched or {}
    official = enriched.get("official_details") or {}
    hay = _text(
        job.get("job_title"), job.get("title"), job.get("employer_name"),
        job.get("location_text"), official.get("job_title"), official.get("location"),
        enriched.get("seo_title"), enriched.get("summary"),
    )
    labels: list[str] = []

    def add(label: str) -> None:
        if label not in labels and len(labels) < 5:
            labels.append(label)

    # Geography
    if any(x in hay for x in ["عمان", "عمّان", "amman"]): add("وظائف عمان")
    elif any(x in hay for x in ["إربد", "اربد", "irbid"]): add("وظائف إربد")
    elif any(x in hay for x in ["الزرقاء", "zarqa"]): add("وظائف الزرقاء")
    elif any(x in hay for x in ["العقبة", "aqaba"]): add("وظائف العقبة")
    else: add("وظائف الأردن")

    # Sector / function
    groups = [
        ("وظائف تقنية", ["تقنية", "برمج", "developer", "software", "integration", "it ", "أنظمة", "شبكات", "data", "cyber"]),
        ("وظائف هندسة", ["مهندس", "هندسة", "engineer", "ميكاني", "كهرب", "صيانة"]),
        ("وظائف مبيعات", ["مبيعات", "sales", "تسويق", "marketing", "خدمة عملاء", "customer service"]),
        ("وظائف محاسبة ومالية", ["محاسب", "محاسبة", "مالي", "finance", "accountant", "بنك", "bank"]),
        ("وظائف إدارية", ["إداري", "اداري", "administr", "موارد بشرية", "hr ", "سكرتار", "مكتب"]),
        ("وظائف صحية", ["طبيب", "ممرض", "صيدل", "medical", "nurse", "health"]),
        ("وظائف تعليم", ["معلم", "مدرس", "teacher", "university", "جامعة", "تعليم"]),
        ("وظائف تشغيلية وفنية", ["فني", "تشغيل", "عامل", "technician", "حداد", "دهان", "بودي"]),
    ]
    for label, tokens in groups:
        if any(token in hay for token in tokens):
            add(label)
            break

    # Experience / audience
    if any(x in hay for x in ["حديثي التخرج", "حديثو التخرج", "خريج جديد", "fresh graduate", "graduate"]):
        add("حديثو التخرج")
    if any(x in hay for x in ["بدون خبرة", "لا يشترط خبرة", "no experience"]):
        add("بدون خبرة")

    # Employer-type labels when confidently signaled
    if any(x in hay for x in ["وزارة", "ديوان", "حكومي", "government", "بلدية"]): add("وظائف حكومية")
    if any(x in hay for x in ["بنك", "bank"]): add("وظائف بنوك")

    if len(labels) < 2:
        add("فرص عمل")
    return labels[:5]


def label_url(label: str) -> str:
    return "/search/label/" + quote(label, safe="")


def category_links(job: dict, enriched: dict | None = None) -> list[tuple[str, str]]:
    return [(label, label_url(label)) for label in classify_labels(job, enriched)]
