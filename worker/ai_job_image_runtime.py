from __future__ import annotations

import ai_job_image as base

_original_build_prompt = base.build_prompt
_original_draw_line = base._draw_line


def _build_prompt(job: dict, title: str) -> str:
    return _original_build_prompt(job, title) + (
        " Show one or two clearly visible professionals actively performing the actual role whenever people are appropriate."
        " Avoid empty rooms and generic empty interiors. Make the job activity immediately recognizable from the image alone."
        " Use a strong photographic subject and an engaging composition while keeping one calm area for the later text overlay."
    )


def _draw_line(draw, xy, text, font, fill, anchor):
    # Avoid decorative Unicode separators that can turn into tofu squares on some runners/fonts.
    safe_text = str(text or "").replace("•", "-").replace("·", "-").replace("▪", "-").replace("▫", "-")
    return _original_draw_line(draw, xy, safe_text, font, fill, anchor)


base.build_prompt = _build_prompt
base._draw_line = _draw_line

generate = base.generate

__all__ = ["generate"]
