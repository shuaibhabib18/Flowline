"""
Workflow Executor — State machine that walks through a workflow step by step.
Handles AUTO steps (via LLM), HUMAN steps (via UI), and DECISION branching.
"""

import json
import os
from pathlib import Path
from .llm import get_llm_client, get_model
from .models import Workflow, Step, StepType, CaseState

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class WorkflowExecutor:
    """Executes a workflow against a specific client case."""

    def __init__(self, workflow: Workflow, api_key: str = None):
        self.workflow = workflow
        self.api_key = api_key
        self.client = get_llm_client(api_key)

    def start_case(self, case_id: str, client_data: dict) -> CaseState:
        """Initialize a new case execution."""
        start = self.workflow.get_start_step()
        state = CaseState(
            case_id=case_id,
            client_data=client_data,
            current_step_id=start.id if start else "",
        )
        return state

    def get_current_step(self, state: CaseState) -> Step | None:
        """Get the step the case is currently on."""
        return self.workflow.get_step(state.current_step_id)

    def execute_auto_step(self, state: CaseState, step: Step) -> dict:
        """Use LLM to execute an AUTO step."""
        if not self.client:
            try:
                from .demo_fixtures import mock_auto_execution

                return mock_auto_execution(step, state)
            except ImportError:
                raise RuntimeError("API key required to execute AUTO steps.")

        prompt = (PROMPTS_DIR / "execute_step.txt").read_text()

        user_msg = json.dumps(
            {
                "current_step": {
                    "title": step.title,
                    "description": step.description,
                    "type": step.step_type.value,
                },
                "client_data": state.client_data,
                "completed_steps": state.completed_steps,
                "previous_results": state.step_results,
            },
            indent=2,
        )

        response = self.client.chat.completions.create(
            model=get_model(),
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        return json.loads(response.choices[0].message.content)

    def advance(
        self,
        state: CaseState,
        decision: str = None,
        human_input: dict = None,
        auto_result: dict = None,
    ) -> CaseState:
        """
        Advance the case to the next step.

        For DECISION steps: provide `decision` (the branch label chosen).
        For HUMAN steps: provide `human_input` (dict of what the human did).
        For AUTO steps: provide `auto_result` (dict from execute_auto_step).
        """
        step = self.get_current_step(state)
        if not step:
            state.status = "completed"
            return state

        # Record step completion
        state.completed_steps.append(state.current_step_id)

        # Store results
        if auto_result:
            state.step_results[state.current_step_id] = auto_result
        elif human_input:
            state.step_results[state.current_step_id] = human_input
        else:
            state.step_results[state.current_step_id] = {"status": "completed"}

        # Determine next step
        if step.step_type == StepType.END:
            state.status = "completed"
            return state

        if step.step_type == StepType.DECISION:
            if decision and decision in step.branches:
                state.decisions_made[state.current_step_id] = decision
                state.current_step_id = step.branches[decision]
            else:
                # If no valid decision provided, block
                state.status = "blocked"
                return state

        elif step.next_steps:
            state.current_step_id = step.next_steps[0]
        else:
            # No next step defined — workflow is done
            state.status = "completed"

        return state

    def get_progress(self, state: CaseState) -> dict:
        """Calculate execution progress."""
        total = len(self.workflow.steps)
        completed = len(state.completed_steps)
        return {
            "completed": completed,
            "total": total,
            "percentage": round((completed / total) * 100) if total > 0 else 0,
            "status": state.status,
            "current_step": state.current_step_id,
            "decisions_made": len(state.decisions_made),
        }
