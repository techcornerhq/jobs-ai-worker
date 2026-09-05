from __future__ import annotations

import copy

import ai_job_image as base

_original_build_prompt = base.build_prompt
_original_draw_line = base._draw_line
_original_generate = base.generate


def _subject_instruction(job: dict, title: str) -> str:
    role = base.first(job.get("job_title"), title, job.get("title"), default="professional job")
    cat, _ = base.visual_category(job, role)
    low = role.lower()
    if cat == "medical":
        if "أشعة" in role or "radiolog" in low:
            return "Main subject MUST be a clearly visible radiologist doctor actively reviewing diagnostic imaging at a modern CT or MRI workstation. "
        return "Main subject MUST be a clearly visible healthcare professional actively performing the medical role in a modern clinical setting. "
    if cat == "technology":
        return "Main subject MUST be a clearly visible technology professional actively coding, configuring systems, or collaborating at a modern workstation. "
    if cat == "education":
        return "Main subject MUST be a clearly visible education or training professional actively teaching, advising, or working in a modern academic setting. "
    if cat == "finance":
        return "Main subject MUST be a clearly visible finance professional actively working with reports, calculations, or business analysis in a refined office. "
    if cat == "office":
        return "Main subject MUST be a clearly visible administrative professional actively organizing work, coordinating, or handling office tasks. "
    if cat == "sales":
        return "Main subject MUST be a clearly visible sales or customer-service professional actively helping a customer in a polished workplace. "
    if cat == "travel":
        return "Main subject MUST be a clearly visible travel or airline reservations professional actively assisting customers with bookings in a premium travel environment. "
    if cat == "industrial":
        return "Main subject MUST be a clearly visible engineer or technician actively performing the relevant industrial or maintenance task with proper safety gear. "
    if cat == "logistics":
        return "Main subject MUST be a clearly visible logistics or inventory professional actively organizing goods in a clean modern warehouse. "
    if cat == "hospitality":
        return "Main subject MUST be a clearly visible hospitality professional actively performing the role in a stylish hotel, cafe, or restaurant setting. "
    if cat == "field":
        return "Main subject MUST be a clearly visible field professional actively performing the role in a realistic Jordanian urban environment. "
    return "Main subject MUST be a clearly visible professional actively performing this job in a realistic modern workplace. "


def _build_prompt(job: dict, title: str) -> str:
    # The image should be driven by the job itself, not by a company logo/building.
    prompt_job = copy.deepcopy(job)
    prompt_job["employer_name"] = ""
    return (
        _subject_instruction(prompt_job, title)
        + _original_build_prompt(prompt_job, title)
        + " Avoid empty rooms and generic empty interiors. Make the actual job activity immediately recognizable from the image alone."
        + " Use a strong photographic subject and an engaging composition while keeping one calm area for the later text overlay."
        + " Prefer a close or medium-wide editorial photograph over an empty architectural shot."
    )


def _draw_line(draw, xy, text, font, fill, anchor):
    # Avoid decorative Unicode separators that can turn into tofu squares on some runners/fonts.
    safe_text = str(text or "")
    for token in ("•", "·", "▪", "▫", "|", "-"):
        safe_text = safe_text.replace(token, "  ")
    return _original_draw_line(draw, xy, safe_text, font, fill, anchor)


def generate(job: dict, title: str):
    # Keep metadata short and readable. Folding location into the employer line with
    # an Arabic comma avoids unsupported separator glyphs and produces a fresh seed.
    j = copy.deepcopy(job)
    employer = base.first(j.get("employer_name"), default="")
    location = base.first(j.get("location_text"), j.get("city"), j.get("governorate"), default="")
    if employer and location:
        j["employer_name"] = f"{employer}، {location}"
        j["location_text"] = ""
        j["city"] = ""
        j["governorate"] = ""
    return _original_generate(j, title)


base.build_prompt = _build_prompt
base._draw_line = _draw_line

__all__ = ["generate"]
