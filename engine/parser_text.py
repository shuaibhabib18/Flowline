"""
Text SOP Parser — Uses LLM to parse unstructured text SOPs into structured workflow graphs.
"""

import json
import os
from pathlib import Path
from .llm import get_llm_client, get_model
from .models import Workflow, Step, StepType

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def parse_text_sop(text: str, api_key: str) -> Workflow:
    """Parse a text SOP into a structured Workflow using GPT-4o."""
    client = get_llm_client(api_key)
    if not client:
        raise ValueError("API key required for text SOP parsing")

    prompt = (PROMPTS_DIR / "parse_sop.txt").read_text()

    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    data = json.loads(response.choices[0].message.content)

    # ── Post-processing: ensure END node exists ──
    steps = data.get("steps", [])
    has_end = any(s.get("type", "").upper() == "END" for s in steps)
    if not has_end and steps:
        # Find terminal steps (no outgoing connections)
        end_id = "end"
        terminal_ids = []
        for s in steps:
            nexts = s.get("next_steps", [])
            branches = s.get("branches", {})
            if not nexts and not branches and s.get("type", "").upper() != "START":
                terminal_ids.append(s["id"])
        # Add END node
        steps.append(
            {
                "id": end_id,
                "title": "Process Complete",
                "description": "Workflow finished.",
                "type": "END",
                "owner": "System",
                "next_steps": [],
                "branches": {},
            }
        )
        # Wire terminal steps to END
        for s in steps:
            if s["id"] in terminal_ids:
                s["next_steps"] = [end_id]
        data["steps"] = steps

    return Workflow.from_dict({**data, "source_format": "text"})
