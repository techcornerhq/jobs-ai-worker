"""Compatibility entrypoint.

The production worker historically imports job_image_v10.generate. Keep that stable
while routing every render through the collision-safe V11 engine.
"""
from job_image_v11 import generate

__all__ = ["generate"]
