from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

@dataclass
class ImageMetadata:
    """Unified structure for parsed genAI metadata (MB data)"""

    file: Path
    workflow_type: Optional[str] = None
    model: Optional[str] = None
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    guidance: Optional[float] = None
    denoise: Optional[float] = None
    seed: Optional[int] = None
    controlnets: List[str] = field(default_factory=list)
    upscale_factor: Optional[float] = None
    style_model: Optional[str] = None
    style_strength: Optional[float] = None
    inpaint_mask_used: Optional[bool] = None
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    nodes: List[str] = field(default_factory=list)
    core_nodes: List[Any] = field(default_factory=list)
    third_party_nodes: List[Any] = field(default_factory=list)
    has_third_party: bool = False
    trusted_workflow: bool = False
    trust_status: Optional[str] = None
    ambiguity_reason: Optional[str] = None
    saveimage_prefixes: List[str] = field(default_factory=list)
    matched_saveimage_prefix: Optional[str] = None
    matched_saveimage_node_id: Optional[str] = None
    raw_json: Optional[Dict] = None
    parsed_ok: bool = True
    error_message: Optional[str] = None

    def as_dict(self):
        d = asdict(self)
        d['file'] = str(self.file)
        return d

    def summary(self) -> str:
        parts = [
            f"Workflow: {self.workflow_type or 'Unknown'}",
            f"Model: {self.model or '—'}",
            f"Steps: {self.steps or '—'}",
            f"CFG: {self.cfg if self.cfg is not None else '—'}",
            f"Denoise: {self.denoise if self.denoise is not None else '—'}",
            f"Seed: {self.seed if self.seed is not None else '—'}",
            f"Trusted: {'yes' if self.trusted_workflow else 'no'}",
        ]
        if self.controlnets:
            parts.append(f"ControlNets: {', '.join(self.controlnets)}")
        if self.matched_saveimage_prefix:
            parts.append(f"SaveImage: {self.matched_saveimage_prefix}")
        if self.ambiguity_reason:
            parts.append(f"Reason: {self.ambiguity_reason}")
        return ' | '.join(parts)
