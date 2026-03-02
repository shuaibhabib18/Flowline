"""
Training Module — Generates training scenarios and quiz questions for workflow steps.
"""

import json
import os
from pathlib import Path
from .llm import get_llm_client, get_model
from .models import Workflow, Step, StepType

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def generate_training_scenario(workflow: Workflow, api_key: str = None) -> dict:
    """Generate a realistic training scenario for this workflow."""
    if not api_key:
        try:
            from .demo_fixtures import get_demo_scenario

            return get_demo_scenario()
        except ImportError:
            raise RuntimeError("API key required to generate training scenarios.")

    client = get_llm_client(api_key)

    prompt = (PROMPTS_DIR / "training_scenario.txt").read_text()

    steps_summary = []
    for step in workflow.steps.values():
        steps_summary.append(
            {
                "id": step.id,
                "title": step.title,
                "type": step.step_type.value,
                "description": step.description,
                "owner": step.owner,
            }
        )

    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "workflow_name": workflow.name,
                        "steps": steps_summary,
                    }
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
    )

    return json.loads(response.choices[0].message.content)


def generate_step_quiz(step: Step, scenario: dict, api_key: str = None) -> dict:
    """Generate a quiz question for a specific step in the workflow."""
    if not api_key:
        try:
            from .demo_fixtures import get_demo_quiz

            return get_demo_quiz(step)
        except ImportError:
            raise RuntimeError("API key required to generate quiz questions.")

    client = get_llm_client(api_key)

    # Load the rich quiz prompt from file
    quiz_prompt_file = PROMPTS_DIR / "training_quiz.txt"
    if quiz_prompt_file.exists():
        system_prompt = quiz_prompt_file.read_text()
    else:
        system_prompt = (
            "Generate a training quiz question for this compliance workflow step. "
            "Return JSON with: question, options (list of 4), correct_index (0-3), explanation."
        )

    # Pick a question format hint to encourage variety across steps
    import hashlib

    seed = int(hashlib.md5(step.id.encode()).hexdigest()[:8], 16)
    format_hints = [
        "Focus on: What is the correct procedural action at this step?",
        "Focus on: Which of these would be a compliance VIOLATION at this step?",
        "Focus on: What MUST be documented during this step?",
        "Focus on: What happens if an exception or error occurs at this step?",
        "Focus on: Which specific regulation or guideline governs this step?",
        "Focus on: What is the PRIMARY purpose and risk this step mitigates?",
        "Focus on: Present a scenario where a trainee makes a subtle mistake — is it correct?",
    ]
    format_hint = format_hints[seed % len(format_hints)]

    response = client.chat.completions.create(
        model=get_model(),
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "step_title": step.title,
                        "step_description": step.description,
                        "step_type": step.step_type.value,
                        "step_owner": step.owner,
                        "scenario": scenario,
                        "question_format_hint": format_hint,
                    },
                    indent=2,
                ),
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.7,
    )

    return json.loads(response.choices[0].message.content)
