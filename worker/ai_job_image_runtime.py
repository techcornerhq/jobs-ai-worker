from __future__ import annotations

import copy

import ai_job_image as base

_original_build_prompt = base.build_prompt
_original_draw_line = base._draw_line
_original_generate = base.generate


def _build_prompt(job: dict, title: str) -> str:
    return _original_build_prompt(job, title) + (
        " Show one or two clearly visible professionals actively performing the actual role whenever people are appropriate."
        " Avoid empty rooms and generic empty interiors. Make the job activity immediately recognizable from the image alone."
        " Use a strong photographic subject and an engaging composition while keeping one calm area for the later text overlay."
        " Prefer a close or medium-wide editorial photograph over an empty architectural shot."
    )


def _draw_line(draw, xy, text, font, fill, anchor):
    # Avoid decorative Unicode separators that can turn into tofu squares on some runners/fonts.
    safe_text = str(text or "")
    for token in ("•", "·", "▪", "▫", "|", "-"):
        safe_text = safe_text.replace(token, "  ")
    return _original_draw_line(draw, xy, safe_text, font, fill, anchor)


def generate(job: dict, title: str):
    # Keep the short metadata line readable without any icon-font or separator glyph.
    # Folding location into the employer line with an Arabic comma also changes the
    # stable seed, so improved prompting gets a fresh scene rather than a cached one.
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
