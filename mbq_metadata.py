from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class ImageMetadata:
    """Unified structure for parsed genAI metadata (MB data)"""

    # Core identifiers
    filename: str
    workflow_type: Optional[str] = None
    model: Optional[str] = None

    # Generation parameters
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    guidance: Optional[float] = None
    denoise: Optional[float] = None
    seed: Optional[int] = None

    # ControlNet / upscale / style / inpaint info
    controlnets: List[str] = field(default_factory=list)
    upscale_factor: Optional[float] = None
    style_model: Optional[str] = None
    style_strength: Optional[float] = None
    inpaint_mask_used: Optional[bool] = None

    # Prompt & text data
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None

    # Detected node list
    nodes: List[str] = field(default_factory=list)

    # Internal / system fields
    raw_json: Optional[Dict] = None
    parsed_ok: bool = True
    error_message: Optional[str] = None

    # Pretty-print helper
    def summary(self) -> str:
        """Simple readable summary for CLI or log output"""
        parts = [
            f"Workflow: {self.workflow_type or 'Unknown'}",
            f"Model: {self.model or '—'}",
            f"Steps: {self.steps or '—'}",
            f"CFG: {self.guidance or '—'}",
            f"Denoise: {self.denoise or '—'}",
            f"Seed: {self.seed or '—'}",
        ]
        if self.controlnets:
            parts.append(f"ControlNets: {', '.join(self.controlnets)}")
        return " | ".join(parts)
