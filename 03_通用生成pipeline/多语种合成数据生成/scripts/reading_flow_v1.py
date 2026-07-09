#!/usr/bin/env python3
"""Template-declared reading flow helpers for VL7.

The generator owns reading order.  The renderer only compiles the attributes
written here into label fields, so crop/augmentation/image replacement cannot
change the human reading sequence.
"""

from __future__ import annotations

import html
import json
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator


NON_OCR_LABELS = {
    "image",
    "answer_area",
    "rule",
    "divider",
    "decorative_rule",
    "table_structure",
    "figure",
    "photo",
    "visual",
}

ROLE_BY_LABEL = {
    "document_title": "title",
    "document_subtitle": "subtitle",
    "section_title": "heading",
    "chapter_title": "heading",
    "paragraph": "body",
    "quote": "quote",
    "caption": "caption",
    "figure_caption": "caption",
    "table_caption": "caption",
    "list_item": "list_item",
    "metadata": "metadata",
    "note": "note",
    "page_number": "page_number",
    "footer": "footer",
    "table_header": "table_header",
    "table_cell_text": "table_cell",
    "field_label": "field_label",
    "field_value": "field_value",
    "question": "question",
}


@dataclass
class FlowContext:
    region: str
    container: str
    role: str = "body"
    parent: str = ""
    direction: str = "ltr"


@dataclass
class FlowBlock:
    block_id: str
    label: str
    path: str
    region: str
    container: str
    role: str
    rank: int
    parent: str
    direction: str
    ocr_orderable: bool
    caption_of: str | None = None


def role_for_label(label: str) -> str:
    return ROLE_BY_LABEL.get(label, label or "text")


def default_orderable(label: str, text: str) -> bool:
    if label in NON_OCR_LABELS:
        return False
    return bool(" ".join(str(text or "").split()))


class FlowPlanner:
    def __init__(self, document_id: str, category: str, variant: int | str, direction: str = "ltr"):
        self.document_id = document_id
        self.category = category
        self.variant = str(variant)
        self.direction = direction or "ltr"
        self.rank = 0
        self.stack: list[FlowContext] = [
            FlowContext(region="body", container="body", role="body", parent="", direction=self.direction)
        ]
        self.blocks: list[FlowBlock] = []
        self.last_visual_block_id: str | None = None

    @contextmanager
    def context(
        self,
        region: str,
        container: str | None = None,
        role: str = "body",
        parent: str | None = None,
        direction: str | None = None,
    ) -> Iterator[None]:
        base = self.stack[-1]
        ctx = FlowContext(
            region=region,
            container=container or region,
            role=role,
            parent=parent if parent is not None else base.container,
            direction=direction or base.direction or self.direction,
        )
        self.stack.append(ctx)
        try:
            yield
        finally:
            self.stack.pop()

    def attrs(
        self,
        block_id: str,
        label: str,
        text: str,
        *,
        flow: str | None = None,
        region: str | None = None,
        container: str | None = None,
        role: str | None = None,
        parent: str | None = None,
        direction: str | None = None,
        ocr_orderable: bool | None = None,
        caption_of: str | None = None,
    ) -> str:
        ctx = self.stack[-1]
        self.rank += 1
        role_value = role or role_for_label(label) or ctx.role
        region_value = region or ctx.region
        container_value = container or ctx.container
        parent_value = parent if parent is not None else ctx.parent
        direction_value = direction or ctx.direction or self.direction
        orderable = default_orderable(label, text) if ocr_orderable is None else bool(ocr_orderable)
        if label in NON_OCR_LABELS:
            orderable = False
        if label == "caption" and caption_of is None and self.last_visual_block_id:
            caption_of = self.last_visual_block_id
        if not flow:
            flow = f"{self.category}/v{self.variant}/{region_value}/{container_value}/{self.rank:04d}_{role_value}"
        item = FlowBlock(
            block_id=block_id,
            label=label,
            path=flow,
            region=region_value,
            container=container_value,
            role=role_value,
            rank=self.rank,
            parent=parent_value,
            direction=direction_value,
            ocr_orderable=orderable,
            caption_of=caption_of,
        )
        self.blocks.append(item)
        if label in {"image", "figure", "photo", "visual"}:
            self.last_visual_block_id = block_id
        parts = {
            "data-flow-path": item.path,
            "data-flow-region": item.region,
            "data-flow-container": item.container,
            "data-flow-role": item.role,
            "data-flow-rank": str(item.rank),
            "data-flow-parent": item.parent,
            "data-flow-direction": item.direction,
            "data-ocr-orderable": "true" if item.ocr_orderable else "false",
        }
        if item.caption_of:
            parts["data-caption-of"] = item.caption_of
        if not item.ocr_orderable:
            parts["data-is-text"] = "false"
        return " ".join(f'{key}="{html.escape(str(value), quote=True)}"' for key, value in parts.items())

    def plan(self) -> dict[str, Any]:
        return {
            "schema": "reading_flow_v1.template_plan",
            "document_id": self.document_id,
            "category": self.category,
            "variant": self.variant,
            "direction": self.direction,
            "blocks": [asdict(block) for block in self.blocks],
        }


def write_template_flow_plan(category_dir: Path, plans: list[dict[str, Any]]) -> None:
    path = category_dir / "metadata" / "template_flow_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plans, ensure_ascii=False, indent=2), encoding="utf-8")

