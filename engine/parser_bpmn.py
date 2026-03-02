"""
BPMN Parser — Parses BPMN 2.0 XML files into structured workflow graphs.
No LLM needed — pure XML parsing.
"""

import xml.etree.ElementTree as ET
from .models import Workflow, Step, StepType


# BPMN 2.0 namespace
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"


def parse_bpmn(filepath: str) -> Workflow:
    """Parse a BPMN 2.0 XML file into a Workflow."""
    tree = ET.parse(filepath)
    root = tree.getroot()

    # Handle namespace prefix variations
    ns = {"bpmn": BPMN_NS}

    # Find the process element
    process = root.find("bpmn:process", ns)
    if process is None:
        # Try without namespace (some exporters don't use prefixes)
        process = root.find(f"{{{BPMN_NS}}}process")
    if process is None:
        # Try bare
        process = root.find("process")
    if process is None:
        raise ValueError("No <process> element found in BPMN file")

    process_name = process.get("name", "Untitled BPMN Process")

    workflow = Workflow(
        name=process_name,
        description=f"Imported from BPMN file",
        source_format="bpmn",
    )

    # -------------------------------------------------------------------------
    # 1. Parse sequence flows (the arrows)
    # -------------------------------------------------------------------------
    flows = {}  # flow_id -> {source, target, label}
    for flow in _find_all(process, "sequenceFlow", ns):
        flow_id = flow.get("id")
        flows[flow_id] = {
            "source": flow.get("sourceRef"),
            "target": flow.get("targetRef"),
            "label": flow.get("name", ""),
        }

    # -------------------------------------------------------------------------
    # 2. Parse lane sets (swimlanes) for owner assignment
    # -------------------------------------------------------------------------
    lane_owners = {}  # element_id -> lane_name
    for lane_set in _find_all(process, "laneSet", ns):
        for lane in _find_all(lane_set, "lane", ns):
            lane_name = lane.get("name", "Unknown")
            for ref in _find_all(lane, "flowNodeRef", ns):
                if ref.text:
                    lane_owners[ref.text.strip()] = lane_name

    # -------------------------------------------------------------------------
    # 3. Parse all BPMN elements into Steps
    # -------------------------------------------------------------------------
    element_type_map = {
        "startEvent": StepType.START,
        "endEvent": StepType.END,
        "task": StepType.HUMAN,
        "userTask": StepType.HUMAN,
        "manualTask": StepType.HUMAN,
        "serviceTask": StepType.AUTO,
        "scriptTask": StepType.AUTO,
        "sendTask": StepType.AUTO,
        "receiveTask": StepType.HUMAN,
        "businessRuleTask": StepType.AUTO,
        "exclusiveGateway": StepType.DECISION,
        "parallelGateway": StepType.DECISION,
        "inclusiveGateway": StepType.DECISION,
        "eventBasedGateway": StepType.DECISION,
        "complexGateway": StepType.DECISION,
        "subProcess": StepType.HUMAN,
        "callActivity": StepType.HUMAN,
        "intermediateThrowEvent": StepType.AUTO,
        "intermediateCatchEvent": StepType.HUMAN,
    }

    for tag, step_type in element_type_map.items():
        for elem in _find_all(process, tag, ns):
            elem_id = elem.get("id")
            name = elem.get("name", elem_id)

            owner = lane_owners.get(
                elem_id, "System" if step_type == StepType.AUTO else "Operator"
            )

            step = Step(
                id=elem_id,
                title=name,
                description=f"BPMN {tag}: {name}",
                step_type=step_type,
                owner=owner,
            )

            # Wire outgoing connections
            if step_type == StepType.DECISION:
                # For gateways, use branches with labels
                for flow in flows.values():
                    if flow["source"] == elem_id:
                        label = flow["label"] or f"→ {flow['target']}"
                        step.branches[label] = flow["target"]
            else:
                # For tasks/events, use next_steps
                for flow in flows.values():
                    if flow["source"] == elem_id:
                        step.next_steps.append(flow["target"])

            workflow.steps[elem_id] = step

    # -------------------------------------------------------------------------
    # 4. Find the start step
    # -------------------------------------------------------------------------
    for step in workflow.steps.values():
        if step.step_type == StepType.START:
            workflow.start_step_id = step.id
            break

    # Fallback: find a step with no incoming flows
    if not workflow.start_step_id:
        incoming = set()
        for flow in flows.values():
            incoming.add(flow["target"])
        for step_id in workflow.steps:
            if step_id not in incoming:
                workflow.start_step_id = step_id
                break

    return workflow


def _find_all(parent: ET.Element, tag: str, ns: dict) -> list[ET.Element]:
    """Find all elements matching a tag, trying namespace variations."""
    # Try with bpmn: prefix
    results = parent.findall(f"bpmn:{tag}", ns)
    if results:
        return results
    # Try with full namespace URI
    results = parent.findall(f"{{{BPMN_NS}}}{tag}")
    if results:
        return results
    # Try bare tag
    return parent.findall(tag)
