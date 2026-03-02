"""
Sample Visio (.vsdx) File Generator — v2

Creates a valid .vsdx with:
  • Three swim lanes  (System · Compliance Officer · Senior Compliance)
  • 14 process shapes  (terminators, rectangles, diamonds)
  • 17 properly-routed connectors with edge-to-edge arrows
  • Full OPC structure for Microsoft Visio 2013+ compatibility

Usage:  python tools/create_sample_visio.py
Output: data/sample_process.vsdx
"""

import zipfile, os
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════════════
# Layout constants
# ══════════════════════════════════════════════════════════════════════════════
PAGE_W, PAGE_H = 11.0, 17.0
LANE_W = 3.5
NS = "http://schemas.microsoft.com/office/visio/2012/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

LANES = {
    "system": {
        "name": "System",
        "cx": 2.0,
        "hdr": "#4472C4",
        "body": "#EBF0F9",
        "txt": "#FFFFFF",
    },
    "compliance": {
        "name": "Compliance Officer",
        "cx": 5.5,
        "hdr": "#548235",
        "body": "#EBF4E5",
        "txt": "#FFFFFF",
    },
    "senior": {
        "name": "Senior Compliance",
        "cx": 9.0,
        "hdr": "#BF8F00",
        "body": "#FDF5E6",
        "txt": "#FFFFFF",
    },
}

# ══════════════════════════════════════════════════════════════════════════════
# Process shapes — (id, visio_name, display_text, lane_key, Y, W, H, type)
# ══════════════════════════════════════════════════════════════════════════════
PROC = [
    (
        "1",
        "Start/End.1",
        "New Client Application Received",
        "system",
        15.5,
        2.2,
        0.5,
        "terminator",
    ),
    (
        "2",
        "Process.2",
        "Retrieve Client Application Data",
        "system",
        14.0,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "3",
        "Process.3",
        "Screen Against Sanctions and PEP Lists",
        "system",
        12.5,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "4",
        "Process.4",
        "Assess Client Risk Level",
        "compliance",
        11.0,
        2.5,
        0.8,
        "rectangle",
    ),
    ("5", "Decision.5", "Is Client High Risk?", "compliance", 9.2, 2.0, 1.2, "diamond"),
    (
        "6",
        "Process.6",
        "Perform Enhanced Due Diligence",
        "senior",
        9.2,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "7",
        "Decision.7",
        "Select Verification Method",
        "compliance",
        7.2,
        2.0,
        1.2,
        "diamond",
    ),
    (
        "8",
        "Process.8",
        "Verify Government-Issued Photo ID",
        "system",
        5.5,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "9",
        "Process.9",
        "Run Credit Bureau Verification",
        "compliance",
        5.5,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "10",
        "Process.10",
        "Conduct Dual-Process Verification",
        "senior",
        5.5,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "11",
        "Decision.11",
        "Identity Verified Successfully?",
        "compliance",
        3.5,
        2.0,
        1.2,
        "diamond",
    ),
    (
        "12",
        "Process.12",
        "Create Compliance Record and Open Account",
        "compliance",
        2.0,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "13",
        "Process.13",
        "Escalate to Senior Compliance Officer",
        "senior",
        2.0,
        2.5,
        0.8,
        "rectangle",
    ),
    (
        "14",
        "Start/End.14",
        "Process Complete",
        "compliance",
        0.5,
        2.2,
        0.5,
        "terminator",
    ),
]

# ══════════════════════════════════════════════════════════════════════════════
# Connectors — (id, from_id, to_id, label, from_side, to_side)
# ══════════════════════════════════════════════════════════════════════════════
CONNS = [
    ("20", "1", "2", "", "bottom", "top"),
    ("21", "2", "3", "", "bottom", "top"),
    ("22", "3", "4", "", "right", "left"),
    ("23", "4", "5", "", "bottom", "top"),
    ("24", "5", "6", "Yes — High Risk", "right", "left"),
    ("25", "5", "7", "No — Standard Risk", "bottom", "top"),
    ("26", "6", "7", "", "bottom", "right"),
    ("27", "7", "8", "Photo ID", "left", "top"),
    ("28", "7", "9", "Credit File", "bottom", "top"),
    ("29", "7", "10", "Dual Process", "right", "top"),
    ("30", "8", "11", "", "bottom", "top"),
    ("31", "9", "11", "", "bottom", "top"),
    ("32", "10", "11", "", "bottom", "top"),
    ("33", "11", "12", "Yes — Verified", "bottom", "top"),
    ("34", "11", "13", "No — Failed", "right", "left"),
    ("35", "12", "14", "", "bottom", "top"),
    ("36", "13", "14", "", "bottom", "top"),
]


# ══════════════════════════════════════════════════════════════════════════════
# Geometry helpers
# ══════════════════════════════════════════════════════════════════════════════
def _rect_geom(w, h):
    return f"""      <Section N="Geometry" IX="0">
        <Cell N="NoFill" V="0"/><Cell N="NoLine" V="0"/><Cell N="NoShow" V="0"/><Cell N="NoSnap" V="0"/>
        <Row T="MoveTo" IX="1"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
        <Row T="LineTo" IX="2"><Cell N="X" V="{w}"/><Cell N="Y" V="0"/></Row>
        <Row T="LineTo" IX="3"><Cell N="X" V="{w}"/><Cell N="Y" V="{h}"/></Row>
        <Row T="LineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="{h}"/></Row>
        <Row T="LineTo" IX="5"><Cell N="X" V="0"/><Cell N="Y" V="0"/></Row>
      </Section>"""


def _diamond_geom(w, h):
    hw, hh = w / 2, h / 2
    return f"""      <Section N="Geometry" IX="0">
        <Cell N="NoFill" V="0"/><Cell N="NoLine" V="0"/><Cell N="NoShow" V="0"/><Cell N="NoSnap" V="0"/>
        <Row T="MoveTo" IX="1"><Cell N="X" V="{hw}"/><Cell N="Y" V="0"/></Row>
        <Row T="LineTo" IX="2"><Cell N="X" V="{w}"/><Cell N="Y" V="{hh}"/></Row>
        <Row T="LineTo" IX="3"><Cell N="X" V="{hw}"/><Cell N="Y" V="{h}"/></Row>
        <Row T="LineTo" IX="4"><Cell N="X" V="0"/><Cell N="Y" V="{hh}"/></Row>
        <Row T="LineTo" IX="5"><Cell N="X" V="{hw}"/><Cell N="Y" V="0"/></Row>
      </Section>"""


def _term_geom(w, h):
    r = min(h / 2, w / 4)
    return f"""      <Section N="Geometry" IX="0">
        <Cell N="NoFill" V="0"/><Cell N="NoLine" V="0"/><Cell N="NoShow" V="0"/><Cell N="NoSnap" V="0"/>
        <Row T="MoveTo" IX="1"><Cell N="X" V="{r}"/><Cell N="Y" V="0"/></Row>
        <Row T="LineTo" IX="2"><Cell N="X" V="{w-r}"/><Cell N="Y" V="0"/></Row>
        <Row T="ArcTo"  IX="3"><Cell N="X" V="{w-r}"/><Cell N="Y" V="{h}"/><Cell N="A" V="{-r*0.55}"/></Row>
        <Row T="LineTo" IX="4"><Cell N="X" V="{r}"/><Cell N="Y" V="{h}"/></Row>
        <Row T="ArcTo"  IX="5"><Cell N="X" V="{r}"/><Cell N="Y" V="0"/><Cell N="A" V="{-r*0.55}"/></Row>
      </Section>"""


GEOM_FN = {"rectangle": _rect_geom, "diamond": _diamond_geom, "terminator": _term_geom}

FILL = {
    "rectangle": ("#DAEEF3", "#B7DEE8"),
    "diamond": ("#FDE9D9", "#FCD5B4"),
    "terminator": ("#D8E4BC", "#C3D69B"),
}


def _edge_pt(shape_row, side):
    """Connection point on a shape edge (page coords)."""
    px, py, w, h = shape_row[4], shape_row[5], shape_row[6], shape_row[7]
    if side == "top":
        return px, py + h / 2
    if side == "bottom":
        return px, py - h / 2
    if side == "left":
        return px - w / 2, py
    if side == "right":
        return px + w / 2, py
    return px, py


# ══════════════════════════════════════════════════════════════════════════════
# Main builder
# ══════════════════════════════════════════════════════════════════════════════
def create_sample_vsdx(output_path: str):
    # ── Expand process shapes with computed PinX ──
    shapes = []
    for sid, name, text, lane, py, w, h, stype in PROC:
        px = LANES[lane]["cx"]
        shapes.append((sid, name, text, lane, px, py, w, h, stype))
    shape_map = {s[0]: s for s in shapes}

    # ── OPC boilerplate (unchanged from v1) ──
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/visio/document.xml" ContentType="application/vnd.ms-visio.drawing.main+xml"/>
  <Override PartName="/visio/pages/pages.xml" ContentType="application/vnd.ms-visio.pages+xml"/>
  <Override PartName="/visio/pages/page1.xml" ContentType="application/vnd.ms-visio.page+xml"/>
  <Override PartName="/visio/windows.xml" ContentType="application/vnd.ms-visio.windows+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"""

    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/document" Target="visio/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""

    core_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
  xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>FINTRAC KYC Identity Verification Process</dc:title>
  <dc:creator>SOP Autopilot</dc:creator>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-02-27T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-02-27T00:00:00Z</dcterms:modified>
</cp:coreProperties>"""

    app_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
  <Application>Microsoft Visio</Application><AppVersion>16.0000</AppVersion>
  <Template>BASICD_M.VSTX</Template>
</Properties>"""

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<VisioDocument xmlns="{NS}" xmlns:r="{RNS}" xml:space="preserve">
  <DocumentSettings TopPage="0" DefaultTextStyle="0" DefaultLineStyle="0" DefaultFillStyle="0">
    <GlueSettings>9</GlueSettings><SnapSettings>65847</SnapSettings>
    <SnapExtensions>34</SnapExtensions><DynamicGridEnabled>1</DynamicGridEnabled>
  </DocumentSettings>
  <Colors>
    <ColorEntry IX="0" RGB="#000000"/><ColorEntry IX="1" RGB="#FFFFFF"/>
    <ColorEntry IX="2" RGB="#FF0000"/><ColorEntry IX="3" RGB="#00FF00"/>
    <ColorEntry IX="4" RGB="#0000FF"/><ColorEntry IX="5" RGB="#FFFF00"/>
  </Colors>
  <FaceNames>
    <FaceName ID="1" Name="Calibri" UnicodeRanges="-536870145 1073786111 1 0" CharSets="536871423 -65536" Panos="2 15 5 2 2 2 4 3 2 4"/>
  </FaceNames>
  <StyleSheets>
    <StyleSheet ID="0" Name="No Style" NameU="No Style">
      <Cell N="LineWeight" V="0.01041666666666667"/><Cell N="LineColor" V="0"/>
      <Cell N="LinePattern" V="1"/><Cell N="FillForegnd" V="1"/>
      <Cell N="FillPattern" V="1"/><Cell N="CharFont" V="1"/>
      <Cell N="CharSize" V="0.1111111111111111" U="IN"/><Cell N="CharColor" V="0"/>
      <Cell N="ParaHorzAlign" V="1"/>
    </StyleSheet>
  </StyleSheets>
</VisioDocument>"""

    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/pages" Target="pages/pages.xml"/>
  <Relationship Id="rId2" Type="http://schemas.microsoft.com/visio/2010/relationships/windows" Target="windows.xml"/>
</Relationships>"""

    pages_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Pages xmlns="{NS}" xmlns:r="{RNS}">
  <Page ID="0" Name="KYC Process Flow" NameU="KYC Process Flow" ViewScale="0.75" ViewCenterX="5.5" ViewCenterY="8.5">
    <PageSheet>
      <Cell N="PageWidth" V="{PAGE_W}" U="IN"/><Cell N="PageHeight" V="{PAGE_H}" U="IN"/>
      <Cell N="DrawingScale" V="1" U="IN"/><Cell N="PageScale" V="1" U="IN"/>
      <Cell N="DrawingSizeType" V="4"/><Cell N="DrawingScaleType" V="0"/>
    </PageSheet>
    <Rel r:id="rId1"/>
  </Page>
</Pages>"""

    pages_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.microsoft.com/visio/2010/relationships/page" Target="page1.xml"/>
</Relationships>"""

    windows_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Windows xmlns="{NS}" xmlns:r="{RNS}" ClientWidth="1920" ClientHeight="1080">
  <Window ID="0" WindowType="Drawing" WindowState="1073742336" WindowLeft="0" WindowTop="0"
    WindowWidth="1920" WindowHeight="1080" ContainerType="Page" Page="0"
    ViewScale="0.75" ViewCenterX="5.5" ViewCenterY="8.5">
    <ShowRulers>1</ShowRulers><ShowGrid>1</ShowGrid><ShowPageBreaks>1</ShowPageBreaks>
    <ShowGuides>1</ShowGuides><ShowConnectionPoints>1</ShowConnectionPoints>
    <GlueSettings>9</GlueSettings><SnapSettings>65847</SnapSettings>
    <SnapExtensions>34</SnapExtensions><DynamicGridEnabled>1</DynamicGridEnabled>
  </Window>
</Windows>"""

    # ══════════════════════════════════════════════════════════════════
    # Build page1.xml shapes
    # ══════════════════════════════════════════════════════════════════
    sx = ""  # shapes XML accumulator

    # ── 1. Swim-lane bodies (drawn first → behind everything) ──
    lane_body_h = 16.0
    lane_body_cy = 8.25  # centre-Y  (spans 0.25 → 16.25)
    lane_hdr_h = 0.6
    lane_hdr_cy = 16.55  # centre-Y  (spans 16.25 → 16.85)
    lane_id = 100

    for key, L in LANES.items():
        cx = L["cx"]
        # Body rectangle — named with "line" so parser treats it as connector (skips it)
        sx += f"""
    <Shape ID="{lane_id}" Name="Swimlane_line.{key}" NameU="Swimlane_line.{key}" Type="Shape">
      <Cell N="PinX" V="{cx}" U="IN"/><Cell N="PinY" V="{lane_body_cy}" U="IN"/>
      <Cell N="Width" V="{LANE_W}" U="IN"/><Cell N="Height" V="{lane_body_h}" U="IN"/>
      <Cell N="LocPinX" V="{LANE_W/2}" U="IN"/><Cell N="LocPinY" V="{lane_body_h/2}" U="IN"/>
      <Cell N="LineWeight" V="0.006944444444444444" U="IN"/><Cell N="LineColor" V="{L['hdr']}"/>
      <Cell N="LinePattern" V="2"/>
      <Cell N="FillForegnd" V="{L['body']}"/><Cell N="FillBkgnd" V="#FFFFFF"/><Cell N="FillPattern" V="1"/>
      <Cell N="BeginX" V="0"/><Cell N="EndX" V="0"/>
{_rect_geom(LANE_W, lane_body_h)}
    </Shape>"""
        lane_id += 1

    # ── 2. Swim-lane headers (on top of bodies) ──
    for key, L in LANES.items():
        cx = L["cx"]
        sx += f"""
    <Shape ID="{lane_id}" Name="Swimlane_header_line.{key}" NameU="Swimlane_header_line.{key}" Type="Shape">
      <Cell N="PinX" V="{cx}" U="IN"/><Cell N="PinY" V="{lane_hdr_cy}" U="IN"/>
      <Cell N="Width" V="{LANE_W}" U="IN"/><Cell N="Height" V="{lane_hdr_h}" U="IN"/>
      <Cell N="LocPinX" V="{LANE_W/2}" U="IN"/><Cell N="LocPinY" V="{lane_hdr_h/2}" U="IN"/>
      <Cell N="LineWeight" V="0.01388888888888889" U="IN"/><Cell N="LineColor" V="{L['hdr']}"/>
      <Cell N="LinePattern" V="1"/>
      <Cell N="FillForegnd" V="{L['hdr']}"/><Cell N="FillBkgnd" V="{L['hdr']}"/><Cell N="FillPattern" V="1"/>
      <Cell N="TxtPinX" V="{LANE_W/2}" U="IN"/><Cell N="TxtPinY" V="{lane_hdr_h/2}" U="IN"/>
      <Cell N="TxtWidth" V="{LANE_W}" U="IN"/><Cell N="TxtHeight" V="{lane_hdr_h}" U="IN"/>
      <Cell N="TxtLocPinX" V="{LANE_W/2}" U="IN"/><Cell N="TxtLocPinY" V="{lane_hdr_h/2}" U="IN"/>
      <Cell N="BeginX" V="0"/><Cell N="EndX" V="0"/>
      <Section N="Character" IX="0">
        <Row IX="0"><Cell N="Font" V="1"/><Cell N="Size" V="0.13888888888888889" U="IN"/>
        <Cell N="Color" V="{L['txt']}"/><Cell N="Style" V="1"/></Row>
      </Section>
      <Section N="Paragraph" IX="0"><Row IX="0"><Cell N="HorzAlign" V="1"/></Row></Section>
{_rect_geom(LANE_W, lane_hdr_h)}
      <Text>{L['name']}</Text>
    </Shape>"""
        lane_id += 1

    # ── 3. Process shapes ──
    for sid, vname, text, lane, px, py, w, h, stype in shapes:
        lx, ly = w / 2, h / 2
        fg, bg = FILL.get(stype, ("#FFFFFF", "#F5F5F5"))
        geom = GEOM_FN[stype](w, h)

        sx += f"""
    <Shape ID="{sid}" Name="{vname}" NameU="{vname}" Type="Shape">
      <Cell N="PinX" V="{px}" U="IN"/><Cell N="PinY" V="{py}" U="IN"/>
      <Cell N="Width" V="{w}" U="IN"/><Cell N="Height" V="{h}" U="IN"/>
      <Cell N="LocPinX" V="{lx}" U="IN"/><Cell N="LocPinY" V="{ly}" U="IN"/>
      <Cell N="Angle" V="0"/><Cell N="FlipX" V="0"/><Cell N="FlipY" V="0"/>
      <Cell N="LineWeight" V="0.01388888888888889" U="IN"/>
      <Cell N="LineColor" V="#333333"/><Cell N="LinePattern" V="1"/>
      <Cell N="Rounding" V="{'0.0625' if stype == 'rectangle' else '0'}" U="IN"/>
      <Cell N="FillForegnd" V="{fg}"/><Cell N="FillBkgnd" V="{bg}"/><Cell N="FillPattern" V="1"/>
      <Cell N="TxtPinX" V="{lx}" U="IN"/><Cell N="TxtPinY" V="{ly}" U="IN"/>
      <Cell N="TxtWidth" V="{w * 0.9}" U="IN"/><Cell N="TxtHeight" V="{h * 0.85}" U="IN"/>
      <Cell N="TxtLocPinX" V="{w * 0.45}" U="IN"/><Cell N="TxtLocPinY" V="{h * 0.425}" U="IN"/>
      <Section N="Character" IX="0">
        <Row IX="0"><Cell N="Font" V="1"/>
        <Cell N="Size" V="0.08333333333333333" U="IN"/><Cell N="Color" V="#333333"/></Row>
      </Section>
      <Section N="Paragraph" IX="0"><Row IX="0"><Cell N="HorzAlign" V="1"/></Row></Section>
{geom}
      <Text>{text}</Text>
    </Shape>"""

    # ── 4. Connector shapes — edge-to-edge with correct geometry ──
    for cid, fid, tid, label, fside, tside in CONNS:
        src, tgt = shape_map[fid], shape_map[tid]
        bx, by = _edge_pt(src, fside)
        ex, ey = _edge_pt(tgt, tside)

        # Bounding box in page coords
        pg_left = min(bx, ex)
        pg_bottom = min(by, ey)
        cw = max(abs(ex - bx), 0.01)
        ch = max(abs(ey - by), 0.01)
        cpx = pg_left + cw / 2
        cpy = pg_bottom + ch / 2

        # Local coordinates (0,0 = bottom-left of bounding box)
        lbx = bx - pg_left
        lby = by - pg_bottom
        lex = ex - pg_left
        ley = ey - pg_bottom

        text_tag = f"<Text>{label}</Text>" if label else ""

        # Fixed text box: always 2" wide × 0.3" tall, centered on connector midpoint
        txt_w = 2.0
        txt_h = 0.3

        sx += f"""
    <Shape ID="{cid}" Name="Dynamic connector.{cid}" NameU="Dynamic connector.{cid}" Type="Shape">
      <Cell N="PinX" V="{cpx}" U="IN"/><Cell N="PinY" V="{cpy}" U="IN"/>
      <Cell N="Width" V="{cw}" U="IN"/><Cell N="Height" V="{ch}" U="IN"/>
      <Cell N="LocPinX" V="{cw/2}" U="IN"/><Cell N="LocPinY" V="{ch/2}" U="IN"/>
      <Cell N="BeginX" V="{bx}" U="IN"/><Cell N="BeginY" V="{by}" U="IN"/>
      <Cell N="EndX" V="{ex}" U="IN"/><Cell N="EndY" V="{ey}" U="IN"/>
      <Cell N="TxtPinX" V="{cw/2}" U="IN"/><Cell N="TxtPinY" V="{ch/2}" U="IN"/>
      <Cell N="TxtWidth" V="{txt_w}" U="IN"/><Cell N="TxtHeight" V="{txt_h}" U="IN"/>
      <Cell N="TxtLocPinX" V="{txt_w/2}" U="IN"/><Cell N="TxtLocPinY" V="{txt_h/2}" U="IN"/>
      <Cell N="TxtAngle" V="0"/>
      <Cell N="LineWeight" V="0.01388888888888889" U="IN"/>
      <Cell N="LineColor" V="#555555"/><Cell N="LinePattern" V="1"/>
      <Cell N="EndArrow" V="4"/><Cell N="EndArrowSize" V="2"/>
      <Cell N="FillPattern" V="0"/>
      <Cell N="LayMember" V="1"/>
      <Cell N="ShapeRouteStyle" V="6"/><Cell N="ConFixedCode" V="6"/>
      <Cell N="ConLineRouteExt" V="1"/>
      <Cell N="BegTrigger" V="2"/><Cell N="EndTrigger" V="2"/>
      <Section N="Character" IX="0">
        <Row IX="0"><Cell N="Font" V="1"/>
        <Cell N="Size" V="0.11111111111111111" U="IN"/><Cell N="Color" V="#555555"/></Row>
      </Section>
      <Section N="Paragraph" IX="0"><Row IX="0"><Cell N="HorzAlign" V="1"/></Row></Section>
      <Section N="Geometry" IX="0">
        <Cell N="NoFill" V="1"/><Cell N="NoLine" V="0"/>
        <Cell N="NoShow" V="0"/><Cell N="NoSnap" V="0"/>
        <Row T="MoveTo" IX="1"><Cell N="X" V="{lbx}"/><Cell N="Y" V="{lby}"/></Row>
        <Row T="LineTo" IX="2"><Cell N="X" V="{lex}"/><Cell N="Y" V="{ley}"/></Row>
      </Section>
      {text_tag}
    </Shape>"""

    # ── 5. Connects section ──
    cx = ""
    for cid, fid, tid, *_ in CONNS:
        cx += f"""
    <Connect FromSheet="{cid}" FromCell="BeginX" ToSheet="{fid}" ToCell="PinX"/>
    <Connect FromSheet="{cid}" FromCell="EndX"   ToSheet="{tid}" ToCell="PinX"/>"""

    page1_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<PageContents xmlns="{NS}" xmlns:r="{RNS}">
  <Shapes>{sx}
  </Shapes>
  <Connects>{cx}
  </Connects>
</PageContents>"""

    # ══════════════════════════════════════════════════════════════════
    # Write ZIP archive
    # ══════════════════════════════════════════════════════════════════
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("docProps/core.xml", core_xml)
        zf.writestr("docProps/app.xml", app_xml)
        zf.writestr("visio/document.xml", document_xml)
        zf.writestr("visio/_rels/document.xml.rels", document_rels)
        zf.writestr("visio/pages/pages.xml", pages_xml)
        zf.writestr("visio/pages/_rels/pages.xml.rels", pages_rels)
        zf.writestr("visio/pages/page1.xml", page1_xml)
        zf.writestr("visio/windows.xml", windows_xml)

    print(f"✅  Created {output_path}")
    print(
        f"    {len(shapes)} process shapes · {len(CONNS)} connectors · {len(LANES)} swim lanes"
    )


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "data" / "sample_process.vsdx"
    create_sample_vsdx(str(out))
