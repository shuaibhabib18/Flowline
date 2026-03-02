"""
Visio Parser — Parses .vsdx files (ZIP archives containing XML) into structured workflow graphs.
No LLM needed — pure XML parsing from the Open Packaging Convention format.
"""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from .models import Workflow, Step, StepType


# Visio 2013+ XML namespace
VISIO_NS = "http://schemas.microsoft.com/office/visio/2012/main"
VISIO_NS_2003 = "http://schemas.microsoft.com/visio/2003/core"


def parse_visio(filepath: str) -> Workflow:
    """
    Parse a .vsdx file into a Workflow.

    .vsdx files are ZIP archives containing XML files:
    - visio/pages/page1.xml — shapes and their text/positions
    - <Connects> section — which connector attaches to which shapes
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    if not zipfile.is_zipfile(filepath):
        raise ValueError(f"Not a valid .vsdx (ZIP) file: {filepath}")

    with zipfile.ZipFile(filepath, "r") as z:
        # Find page XML files
        page_files = sorted(
            [
                f
                for f in z.namelist()
                if "pages/page" in f.lower() and f.endswith(".xml") and "_rels" not in f
            ]
        )

        if not page_files:
            raise ValueError("No page files found in .vsdx archive")

        # Parse the first page (primary process diagram)
        page_xml = z.read(page_files[0])
        root = ET.fromstring(page_xml)

        # Detect namespace
        ns_uri = _detect_namespace(root)
        ns = {"v": ns_uri} if ns_uri else {}

        # Extract shapes
        shapes, connector_shapes = _extract_shapes(root, ns)

        # Extract connections
        connections = _extract_connections(root, ns)

        # Build workflow
        workflow = _build_workflow(shapes, connector_shapes, connections)

        return workflow


def _detect_namespace(root: ET.Element) -> str:
    """Detect which Visio namespace the file uses."""
    tag = root.tag
    if VISIO_NS in tag:
        return VISIO_NS
    if VISIO_NS_2003 in tag:
        return VISIO_NS_2003
    # Check for namespace in attributes
    for ns_uri in [VISIO_NS, VISIO_NS_2003]:
        if root.find(f".//{{{ns_uri}}}Shape") is not None:
            return ns_uri
    return VISIO_NS  # Default


def _extract_shapes(root: ET.Element, ns: dict) -> tuple[dict, dict]:
    """
    Extract all shapes from the page XML.
    Returns (content_shapes, connector_shapes) — separated.
    """
    shapes = {}  # shape_id -> shape data
    connector_shapes = {}  # connector_id -> connector data

    for shape in _find_elements(root, ".//Shape", ns):
        shape_id = shape.get("ID")
        if not shape_id:
            continue

        name_attr = shape.get("Name", "") or shape.get("NameU", "")
        master_id = shape.get("Master", "")

        # Extract text content
        text = _get_shape_text(shape, ns)

        # Extract position
        pin_x, pin_y, width, height = _get_shape_geometry(shape, ns)

        # Determine if this is a connector (arrow) or a content shape
        is_connector = _is_connector_shape(shape, name_attr, ns)

        if is_connector:
            connector_shapes[shape_id] = {
                "text": text,
                "name": name_attr,
            }
        else:
            step_type = _classify_shape(name_attr, text, master_id)
            shapes[shape_id] = {
                "id": f"visio_{shape_id}",
                "text": text or f"Shape {shape_id}",
                "name": name_attr,
                "master": master_id,
                "x": pin_x,
                "y": pin_y,
                "width": width,
                "height": height,
                "type": step_type,
            }

    return shapes, connector_shapes


def _extract_connections(root: ET.Element, ns: dict) -> dict:
    """
    Extract connections from the <Connects> section.

    Each arrow in Visio generates TWO <Connect> entries:
    - One for BeginX (arrow start) → which shape it comes FROM
    - One for EndX (arrow end) → which shape it goes TO

    We pair them by connector shape ID (FromSheet).
    """
    connections = {}  # connector_id -> {"from": shape_id, "to": shape_id}

    for connect in _find_elements(root, ".//Connect", ns):
        connector_id = connect.get("FromSheet")
        from_cell = connect.get("FromCell", "")
        to_sheet = connect.get("ToSheet")

        if not connector_id or not to_sheet:
            continue

        if connector_id not in connections:
            connections[connector_id] = {}

        # BeginX = where the arrow STARTS (source shape)
        # EndX = where the arrow ENDS (target shape)
        if "Begin" in from_cell:
            connections[connector_id]["from"] = to_sheet
        elif "End" in from_cell:
            connections[connector_id]["to"] = to_sheet

    return connections


def _build_workflow(
    shapes: dict, connector_shapes: dict, connections: dict
) -> Workflow:
    """Assemble a Workflow from extracted shapes and connections."""
    workflow = Workflow(
        name="Imported Visio Process",
        description="Parsed from .vsdx file — shapes and connections extracted from XML",
        source_format="visio",
    )

    # Create steps from content shapes
    for shape_id, shape_data in shapes.items():
        step = Step(
            id=shape_data["id"],
            title=shape_data["text"],
            description=f"Visio shape '{shape_data['name']}' at position ({shape_data['x']:.1f}, {shape_data['y']:.1f})",
            step_type=shape_data["type"],
            owner=_infer_owner(shape_data["type"], shape_data["text"]),
        )
        workflow.steps[step.id] = step

    # Wire up connections using the paired Connect entries
    for conn_id, conn in connections.items():
        if "from" not in conn or "to" not in conn:
            continue

        from_id = f"visio_{conn['from']}"
        to_id = f"visio_{conn['to']}"

        if from_id not in workflow.steps or to_id not in workflow.steps:
            continue

        from_step = workflow.steps[from_id]

        if from_step.step_type == StepType.DECISION:
            # Use connector's text as the branch label
            label = connector_shapes.get(conn_id, {}).get("text", "")
            if not label:
                label = f"Option {len(from_step.branches) + 1}"
            from_step.branches[label] = to_id
        else:
            if to_id not in from_step.next_steps:
                from_step.next_steps.append(to_id)

    # Find start step: shape with no incoming connections
    incoming = set()
    for conn in connections.values():
        if "to" in conn:
            incoming.add(f"visio_{conn['to']}")

    for step_id in workflow.steps:
        if step_id not in incoming:
            step = workflow.steps[step_id]
            if step.step_type == StepType.START:
                workflow.start_step_id = step_id
                break

    # Fallback: first non-incoming step
    if not workflow.start_step_id:
        for step_id in workflow.steps:
            if step_id not in incoming:
                workflow.start_step_id = step_id
                break

    # Last fallback: topmost shape (highest Y coordinate)
    if not workflow.start_step_id and shapes:
        sorted_shapes = sorted(shapes.values(), key=lambda s: -s["y"])
        workflow.start_step_id = sorted_shapes[0]["id"]

    return workflow


# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────


def _find_elements(root: ET.Element, path: str, ns: dict) -> list[ET.Element]:
    """Find elements trying both namespaced and bare versions."""
    if ns:
        ns_uri = list(ns.values())[0]
        # Try with namespace
        tag = path.split("//")[-1] if "//" in path else path
        results = root.findall(f".//{{{ns_uri}}}{tag}")
        if results:
            return results
        # Try with prefix
        ns_path = path.replace("//", f"//{list(ns.keys())[0]}:")
        results = root.findall(ns_path, ns)
        if results:
            return results
    return root.findall(path)


def _get_shape_text(shape: ET.Element, ns: dict) -> str:
    """Extract text content from a shape element."""
    ns_uri = list(ns.values())[0] if ns else ""

    # Try various text element locations
    for text_path in [f"{{{ns_uri}}}Text", "Text", f".//{{{ns_uri}}}Text", ".//Text"]:
        text_elem = shape.find(text_path)
        if text_elem is not None:
            return "".join(text_elem.itertext()).strip()
    return ""


def _get_shape_geometry(
    shape: ET.Element, ns: dict
) -> tuple[float, float, float, float]:
    """Extract PinX, PinY, Width, Height from Cell elements."""
    ns_uri = list(ns.values())[0] if ns else ""
    values = {"PinX": 0.0, "PinY": 0.0, "Width": 1.0, "Height": 0.75}

    for cell_path in [f"{{{ns_uri}}}Cell", "Cell"]:
        for cell in shape.findall(cell_path):
            cell_name = cell.get("N", "")
            if cell_name in values:
                try:
                    values[cell_name] = float(cell.get("V", 0))
                except (ValueError, TypeError):
                    pass

    return values["PinX"], values["PinY"], values["Width"], values["Height"]


def _is_connector_shape(shape: ET.Element, name: str, ns: dict) -> bool:
    """Determine if a shape is a connector (arrow) rather than a content shape."""
    name_lower = name.lower()
    if any(kw in name_lower for kw in ["connector", "dynamic", "arrow", "line"]):
        return True

    # Check for BeginX/EndX cells (connector indicators)
    ns_uri = list(ns.values())[0] if ns else ""
    for cell_path in [f"{{{ns_uri}}}Cell", "Cell"]:
        for cell in shape.findall(cell_path):
            if cell.get("N") in ("BeginX", "EndX"):
                return True

    return False


def _classify_shape(name: str, text: str, master_id: str) -> StepType:
    """Classify a Visio shape into a StepType based on its name and text."""
    name_lower = name.lower()
    text_lower = text.lower()

    # Shape name patterns (from Visio stencils)
    if any(kw in name_lower for kw in ["start", "begin", "start/end"]):
        if any(kw in text_lower for kw in ["start", "begin", "new", "receive"]):
            return StepType.START
        elif any(kw in text_lower for kw in ["end", "complete", "finish", "done"]):
            return StepType.END
        # Ambiguous start/end shape — check position later
        return StepType.START

    if any(kw in name_lower for kw in ["terminator"]):
        return StepType.END

    if any(kw in name_lower for kw in ["decision", "diamond", "gateway", "exclusive"]):
        return StepType.DECISION

    # Text-based classification
    if "?" in text:
        return StepType.DECISION

    if any(
        kw in text_lower
        for kw in [
            "auto",
            "system",
            "generate",
            "send notification",
            "retrieve",
            "lookup",
            "query",
            "create record",
            "store",
            "log",
            "screen against",
        ]
    ):
        return StepType.AUTO

    if any(
        kw in text_lower
        for kw in [
            "review",
            "verify",
            "confirm",
            "approve",
            "inspect",
            "interview",
            "assess",
            "check",
            "examine",
            "officer",
        ]
    ):
        return StepType.HUMAN

    return StepType.HUMAN  # Default to human (safer assumption)


def _infer_owner(step_type: StepType, text: str) -> str:
    """Infer the step owner from its type and text content."""
    text_lower = text.lower()

    if step_type in (StepType.AUTO, StepType.START, StepType.END):
        return "System"

    if "senior" in text_lower:
        return "Senior Compliance Officer"
    if "compliance" in text_lower or "officer" in text_lower:
        return "Compliance Officer"
    if "manager" in text_lower:
        return "Manager"

    return "Operator"
