from __future__ import annotations

import re

import job_image_v6 as base
from company_visual import fetch_official_photo

_ALLOWED = re.compile(r"[^\u0600-\u06FFA-Za-z0-9\s.,:؛،()/%+\-]", re.UNICODE)


def safe_text(value: str) -> str:
    s = str(value or "")
    s = s.replace("–", "-").replace("—", "-").replace("|", " - ")
    s = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\ufeff]", "", s)
    s = _ALLOWED.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def arabic_job_phrase(text: str) -> str:
    s = safe_text(text)
    replacements = [
        (r"Integration\s+Developer(?:\s+Team\s+Member)?", "مطور تكامل أنظمة"),
        (r"Integration\s+Developer", "مطور تكامل أنظمة"),
        (r"Team\s+Member", ""),
        (r"Developer", "مطور برمجيات"),
        (r"Software\s+Engineer", "مهندس برمجيات"),
        (r"Engineer", "مهندس"),
    ]
    for pattern, repl in replacements:
        s = re.sub(pattern, repl, s, flags=re.I)
    return safe_text(s)


def display_employer(value: str) -> str:
    e = safe_text(value)
    if "المناصير" in e or "العاديات السريعة" in e:
        return "مجموعة المناصير"
    if "زين" in e or re.search(r"\bZain\b", e, re.I):
        return "زين الأردن"
    if "العميد" in e or re.search(r"\bAlameed\b", e, re.I):
        return "بن العميد"
    e = re.sub(r"\s*\([^)]*\)\s*", " ", e)
    return safe_text(e)[:42] or "جهة توظيف"


def headline(title: str, employer: str):
    emp = display_employer(employer)
    t = arabic_job_phrase(title)
    t = re.sub(r"\s*[-:]?\s*(?:ب?رواتب?|راتب)\s+متوقعة?.*$", "", t).strip(" :-")
    for token in [emp, safe_text(employer), "زين الأردن", "بن العميد", "مجموعة المناصير"]:
        if token and token in t:
            t = t.replace(token, "", 1).strip(" :-")
            break
    t = re.sub(r"^(?:تعلن عن|تعلن|تفتح باب التوظيف|تطلب موظفين|توظف)\s*", "", t).strip()
    if "زين" in emp:
        t = "فرصة عمل لمطور تكامل أنظمة في عمان"
    elif "العميد" in emp:
        t = "14 شاغرا متنوعا في عمان"
    elif "المناصير" in emp:
        t = "توظيف في تخصصات الصيانة والهندسة الميكانيكية"
    elif not t:
        t = "فرص عمل جديدة"
    elif not t.startswith(("فرص", "وظائف", "شواغر", "مطلوب", "فرصة", "توظيف")):
        t = "فرص عمل " + t
    return emp, safe_text(t)


def departments(title: str) -> str:
    t = arabic_job_phrase(title)
    if any(x in t for x in ["تكامل", "مطور", "تقنية", "برمج"]):
        return "التخصص: تطوير وتكامل الأنظمة التقنية"
    if any(x in t for x in ["صيانة", "ميكاني", "كهرب", "حدادة", "دهان", "بودي"]):
        return "التخصصات: صيانة، ميكانيك، كهرباء، حدادة وهندسة ميكانيكية"
    if "العميد" in t or "متنوعة" in t:
        return "الأقسام: إدارية، تقنية، تشغيلية، مبيعات وخدمة عملاء"
    return "التفاصيل والتخصصات موضحة داخل الإعلان"


def generate(job: dict, title: str):
    original_fetch = base.fetch_company_photo
    original_clean = base.clean
    original_headline = base.headline
    original_departments = base.departments
    base.IMAGE_VERSION = "v8"
    base.fetch_company_photo = lambda j: fetch_official_photo(j) or original_fetch(j)
    base.clean = safe_text
    base.headline = headline
    base.departments = departments
    try:
        return base.generate(job, arabic_job_phrase(title))
    finally:
        base.fetch_company_photo = original_fetch
        base.clean = original_clean
        base.headline = original_headline
        base.departments = original_departments
