"""
Flowline — Intelligent SOP Execution Engine
Streamlit application for parsing, executing, and training on SOPs.

Supports three input formats:
  • Text SOP (parsed via LLM)
  • BPMN 2.0 XML (parsed via XML extraction)
  • Visio .vsdx (parsed via ZIP + XML extraction)

All three converge to the same Workflow graph → same Executor → same Training mode.
"""

import csv
import io
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import graphviz
import streamlit as st
from dotenv import load_dotenv

from engine.models import Workflow, Step, StepType, CaseState
from engine.parser_text import parse_text_sop
from engine.parser_bpmn import parse_bpmn

try:
    from engine.demo_fixtures import get_demo_workflow
except ImportError:
    get_demo_workflow = None
from engine.parser_visio import parse_visio
from engine.executor import WorkflowExecutor
from engine.training import generate_training_scenario, generate_step_quiz

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
load_dotenv(BASE_DIR / ".env")

CASES_HISTORY_FILE = DATA_DIR / "cases_history.json"


def _load_cases_history() -> list:
    """Load persisted case history from disk."""
    if CASES_HISTORY_FILE.exists():
        try:
            return json.loads(CASES_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_cases_history(history: list):
    """Persist case history to disk."""
    try:
        CASES_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except OSError:
        pass


TRAINING_HISTORY_FILE = DATA_DIR / "training_history.json"


def _load_training_history() -> list:
    """Load persisted training history from disk."""
    if TRAINING_HISTORY_FILE.exists():
        try:
            return json.loads(TRAINING_HISTORY_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_training_history(history: list):
    """Persist training history to disk."""
    try:
        TRAINING_HISTORY_FILE.write_text(json.dumps(history, indent=2))
    except OSError:
        pass


st.set_page_config(
    page_title="Flowline",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS — Wealthsimple-aligned Design System
st.markdown(
    """
<style>
    /* ── Force Light Mode ────────────────────────── */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        color: #0A0A0A !important;
        background-color: #ffffff !important;
    }
    [data-testid="stSidebar"], section[data-testid="stSidebar"] > div {
        background: #f5f5f3 !important;
        color: #0A0A0A !important;
    }
    [data-testid="stHeader"] { background: #ffffff !important; }
    .main .block-container { background: #ffffff !important; }
    p, span, label, .stMarkdown, .stText, .stCaption, li, td, th {
        color: #0A0A0A !important;
    }

    /* ── Color Palette (Wealthsimple) ──────────────── */
    :root {
        --ws-yellow: #FFC629;
        --ws-yellow-light: #FFD54F;
        --ws-yellow-dark: #E5AD00;
        --ws-black: #0A0A0A;
        --ws-dark: #1A1A1A;
        --ws-green: #00A67E;
        --ws-red: #E5484D;
        --ws-orange: #F5A623;
        --bg-card: #ffffff;
        --bg-subtle: #f5f5f3;
        --text-primary: #0A0A0A;
        --text-secondary: #6B6B6B;
        --border: #E8E8E4;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
        --radius: 10px;
    }

    /* ── Global Typography ─────────────────────────── */
    .main .block-container { max-width: 1200px; padding-top: 2rem; }
    h1, h2, h3 { color: var(--text-primary) !important; font-weight: 700 !important; letter-spacing: -0.02em; }

    /* ── Tab Styling ───────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        background: var(--bg-subtle);
        padding: 4px;
        border-radius: var(--radius);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 24px;
        border-radius: 8px;
        font-weight: 600;
        font-size: 0.9rem;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { background: rgba(255, 198, 41, 0.1); }
    .stTabs [aria-selected="true"] { background: #ffffff !important; box-shadow: var(--shadow-sm); }

    /* ── Metric Cards ──────────────────────────────── */
    [data-testid="stMetric"] {
        background: #ffffff;
        padding: 16px 20px;
        border-radius: var(--radius);
        border: 1px solid var(--border);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
    }
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-secondary) !important; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; font-weight: 800; color: var(--text-primary) !important; }

    /* ── Buttons (WS style: dark primary, clean secondary) ── */
    .stButton > button[kind="primary"],
    .stButton > button[kind="primary"]:focus,
    .stButton > button[kind="primary"]:active {
        background-color: #0A0A0A !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span {
        color: #ffffff !important;
    }
    .stFormSubmitButton > button,
    .stFormSubmitButton > button:focus,
    .stFormSubmitButton > button:active,
    .stFormSubmitButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"]:focus,
    .stFormSubmitButton > button[kind="primary"]:active {
        background-color: #0A0A0A !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .stFormSubmitButton > button p,
    .stFormSubmitButton > button span,
    .stFormSubmitButton > button[kind="primary"] p,
    .stFormSubmitButton > button[kind="primary"] span {
        color: #ffffff !important;
    }
    .stFormSubmitButton > button:hover,
    .stFormSubmitButton > button[kind="primary"]:hover {
        background-color: #333333 !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }
    .stButton > button[kind="primary"]:hover {
        background-color: #333333 !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }
    .stButton > button[kind="secondary"] {
        background-color: #555555 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span {
        color: #ffffff !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background-color: #6a6a6a !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }

    /* ── Expanders (add inner padding) ──────────────── */
    .streamlit-expanderHeader {
        font-weight: 600 !important;
        font-size: 0.95rem;
        border-radius: var(--radius) !important;
    }
    [data-testid="stExpander"] [data-testid="stVerticalBlock"] {
        padding: 2px 8px !important;
    }

    /* ── Sidebar ────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #f5f5f3;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 0.6rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    section[data-testid="stSidebar"] .stDivider { margin: 6px 0; opacity: 0.3; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        gap: 0.2rem !important;
    }
    section[data-testid="stSidebar"] [data-testid="stMetric"] {
        padding: 8px 12px;
    }
    section[data-testid="stSidebar"] .stRadio > div { gap: 2px !important; }
    section[data-testid="stSidebar"] .stRadio label { padding: 3px 0 !important; font-size: 0.88rem; }
    section[data-testid="stSidebar"] .stCheckbox { margin: 0 !important; }
    section[data-testid="stSidebar"] h3 { font-size: 0.72rem !important; margin: 0 !important; padding: 0 !important; text-transform: uppercase; letter-spacing: 0.1em; color: #999 !important; font-weight: 700 !important; }
    section[data-testid="stSidebar"] .stCaption { margin: 0 !important; }
    section[data-testid="stSidebar"] .stAlert { padding: 6px 10px !important; font-size: 0.82rem; margin: 0 !important; border-radius: 8px !important; }

    /* ── Progress Bar ───────────────────────────────── */
    .stProgress > div > div { background: linear-gradient(90deg, var(--ws-yellow) 0%, var(--ws-green) 100%) !important; border-radius: 8px; }
    .stProgress p, .stProgress span { padding-left: 0.6rem !important; }

    /* ── Dataframe ──────────────────────────────────── */
    .stDataFrame { border-radius: var(--radius); overflow: hidden; border: 1px solid var(--border); }

    /* ── Download Buttons ───────────────────────────── */
    .stDownloadButton > button {
        background-color: #555555 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        border: none !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    .stDownloadButton > button p,
    .stDownloadButton > button span {
        color: #ffffff !important;
    }
    .stDownloadButton > button:hover {
        background-color: #6a6a6a !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08) !important;
    }

    /* ── Empty state cards ──────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 48px 32px;
        background: var(--bg-subtle) !important;
        color: var(--text-primary) !important;
        border-radius: var(--radius);
        border: 2px dashed var(--border);
    }
    .empty-state h3 { margin: 16px 0 8px 0; color: var(--text-primary) !important; }
    .empty-state p { color: var(--text-secondary) !important; margin: 0; }

    /* ── Multiselect Pills ──────────────────────────── */
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: #0A0A0A !important;
        color: #ffffff !important;
    }
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] span,
    [data-testid="stMultiSelect"] span[data-baseweb="tag"] div {
        color: #ffffff !important;
    }

    /* ── Force Inputs ──────────────────────────────── */
    input, textarea, select, [data-baseweb] {
        color: #0A0A0A !important;
    }
    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox [data-baseweb="select"] > div,
    .stSelectbox [data-baseweb="select"],
    section[data-testid="stSidebar"] .stTextInput input,
    section[data-testid="stSidebar"] .stTextArea textarea,
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] .stSelectbox [data-baseweb="select"] {
        background-color: #ffffff !important;
        background: #ffffff !important;
        color: #0A0A0A !important;
    }
    .stSelectbox label, .stTextInput label, .stTextArea label,
    .stRadio label, .stCheckbox label, .stFileUploader label {
        color: var(--text-primary) !important;
    }

    /* ── Placeholder Text ──────────────────────────── */
    input::placeholder, textarea::placeholder {
        color: #999999 !important;
        opacity: 1 !important;
    }
    .stTextInput input::placeholder,
    .stTextArea textarea::placeholder,
    section[data-testid="stSidebar"] .stTextInput input::placeholder,
    section[data-testid="stSidebar"] .stTextArea textarea::placeholder {
        color: #999999 !important;
        opacity: 1 !important;
    }

    /* ── File Uploader Browse Button ───────────────── */
    .stFileUploader button,
    .stFileUploader [data-testid="stBaseButton-secondary"],
    section[data-testid="stSidebar"] .stFileUploader button,
    section[data-testid="stSidebar"] .stFileUploader [data-testid="stBaseButton-secondary"] {
        background-color: #ffffff !important;
        color: #0A0A0A !important;
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }
    .stFileUploader button p,
    .stFileUploader button span,
    section[data-testid="stSidebar"] .stFileUploader button p,
    section[data-testid="stSidebar"] .stFileUploader button span {
        color: #0A0A0A !important;
    }
    .stFileUploader button:hover,
    section[data-testid="stSidebar"] .stFileUploader button:hover {
        background-color: #f5f5f3 !important;
        color: #0A0A0A !important;
        border: 1px solid #ccc !important;
    }
    .stFileUploader,
    .stFileUploader div,
    .stFileUploader span,
    .stFileUploader small,
    .stFileUploader section,
    section[data-testid="stSidebar"] .stFileUploader section {
        color: #0A0A0A !important;
    }

    /* ── Sidebar Library Cards ─────────────────────── */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        padding: 4px 8px !important;
        background: #ffffff !important;
        margin-bottom: 6px !important;
    }

    /* ── Popover Trigger (API Key button) ──────────── */
    .stPopover > button,
    .stPopover > [data-testid="stBaseButton-secondary"],
    section[data-testid="stSidebar"] .stPopover > button {
        background-color: #ffffff !important;
        color: #0A0A0A !important;
        border: 1px solid #ddd !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: none !important;
    }
    .stPopover > button p,
    .stPopover > button span,
    section[data-testid="stSidebar"] .stPopover > button p,
    section[data-testid="stSidebar"] .stPopover > button span {
        color: #0A0A0A !important;
    }
    .stPopover > button:hover,
    section[data-testid="stSidebar"] .stPopover > button:hover {
        background-color: #f5f5f3 !important;
        border: 1px solid #ccc !important;
    }
    /* Popover panel background */
    [data-testid="stPopoverBody"],
    div[data-baseweb="popover"] > div {
        background-color: #ffffff !important;
        color: #0A0A0A !important;
        border: 1px solid #ddd !important;
        border-radius: 10px !important;
    }
    [data-testid="stPopoverBody"] input {
        background-color: #ffffff !important;
        color: #0A0A0A !important;
        border: 1px solid #ddd !important;
    }

    /* ── Expander text ─────────────────────────────── */
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] div { color: var(--text-primary) !important; }

    /* ── Logo ───────────────────────────────────────── */
    .fl-brand {
        padding: 4px 0 8px 0;
    }
    .fl-logo {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        color: #0A0A0A;
        line-height: 1.1;
        margin: 0;
        padding: 0;
    }
    .fl-logo .fl-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 28px;
        height: 28px;
        background: #0A0A0A;
        border-radius: 7px;
        margin-right: 6px;
        position: relative;
        top: -1px;
        vertical-align: middle;
    }
    .fl-logo .fl-icon svg {
        width: 16px;
        height: 16px;
    }
    .fl-logo .fl-mark {
        display: inline-block;
        width: 10px;
        height: 10px;
        background: #FFC629;
        border-radius: 50%;
        margin-left: 2px;
        vertical-align: baseline;
        position: relative;
        top: -2px;
    }
    .fl-tagline {
        font-size: 0.82rem;
        color: #999;
        letter-spacing: 0.03em;
        margin: 4px 0 0 0;
        padding: 0;
        font-weight: 500;
    }
    .fl-section-label {
        font-size: 0.7rem;
        font-weight: 700;
        color: #999;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin: 8px 0 4px 0;
        padding: 0;
    }



    /* ── View Toggle ────────────────────────────────── */
    .view-toggle {
        display: inline-flex;
        background: #f5f5f3;
        border-radius: 10px;
        padding: 4px;
        gap: 4px;
    }
    .view-toggle-btn {
        padding: 8px 20px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #6B6B6B;
        cursor: pointer;
        text-decoration: none;
        transition: all 0.2s ease;
    }
    .view-toggle-btn.active {
        background: #ffffff;
        color: #0A0A0A;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }

    /* ── Path Selection Cards ──────────────────────── */
    .path-cards {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1.5rem;
        margin: 1.5rem 0 2rem 0;
    }
    .path-card {
        background: #ffffff;
        border: 2px solid #E8E8E4;
        border-radius: 16px;
        padding: 2rem;
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .path-card:hover {
        border-color: #FFC629;
        box-shadow: 0 8px 24px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }
    .path-card-icon {
        width: 48px;
        height: 48px;
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.4rem;
        margin-bottom: 1rem;
    }
    .path-card h3 {
        margin: 0 0 0.5rem 0 !important;
        font-size: 1.2rem !important;
    }
    .path-card p {
        margin: 0;
        color: #6B6B6B !important;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .path-card .path-steps {
        margin-top: 1rem;
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8rem;
        color: #999;
        font-weight: 600;
    }

    /* ── Top Bar ────────────────────────────────────── */
    .top-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }

    /* ── Pipeline Stepper ───────────────────────────── */
    .pipeline-stepper {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0;
        padding: 16px 24px;
        margin-bottom: 8px;
        background: #f5f5f3;
        border-radius: 12px;
        border: 1px solid #E8E8E4;
    }
    .ps-step {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #999;
        transition: all 0.2s ease;
    }
    .ps-step.active {
        background: #ffffff;
        color: #0A0A0A;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .ps-step.done {
        color: #00A67E;
    }
    .ps-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border-radius: 50%;
        font-size: 0.75rem;
        font-weight: 700;
        background: #E8E8E4;
        color: #999;
        flex-shrink: 0;
    }
    .ps-step.active .ps-num {
        background: #0A0A0A;
        color: #ffffff;
    }
    .ps-step.done .ps-num {
        background: #00A67E;
        color: #ffffff;
    }
    .ps-arrow {
        margin: 0 4px;
        color: #ccc;
        font-size: 1rem;
        flex-shrink: 0;
    }

    /* ── Configure tab cards ────────────────────────── */
    .cfg-card {
        background: #ffffff;
        border: 1px solid #E8E8E4;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 12px;
        transition: box-shadow 0.15s ease;
    }
    .cfg-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }
    .cfg-card-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 12px;
    }
    .cfg-type-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .cfg-type-auto { background: #E8F5E9; color: #2E7D32; }
    .cfg-type-human { background: #E3F2FD; color: #1565C0; }
    .cfg-type-decision { background: #FFF3E0; color: #E65100; }
    .cfg-type-start { background: #F3E5F5; color: #7B1FA2; }
    .cfg-type-end { background: #ECEFF1; color: #546E7A; }
    .cfg-saved-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 0.7rem;
        font-weight: 600;
        background: #E8F5E9;
        color: #2E7D32;
        margin-left: auto;
    }

    /* ── Sidebar library cards ──────────────────── */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] > div[data-testid="stVerticalBlock"] {
        padding: 6px 10px !important;
        gap: 0.15rem !important;
    }
    /* segmented toggle polish */
    [data-testid='stHorizontalBlock'] button[disabled] {
        opacity: 1 !important;
    }

    /* ── Sidebar file-uploader cleanup ─────────── */
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] {
        background: #fff !important;
        border: 1.5px dashed #ccc !important;
        border-radius: 10px !important;
        padding: 12px 10px !important;
        gap: 4px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] section {
        padding: 4px 0 !important;
    }
    section[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
        font-size: 0.82rem !important;
        border-radius: 8px !important;
    }
    /* active-doc card */
    .active-doc-card {
        background: linear-gradient(135deg, #f0f7ff 0%, #e8f0fe 100%);
        border: 1px solid #c6daf7;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 4px 0 2px 0;
    }
    .active-doc-card .doc-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #6b7280;
        font-weight: 600;
        margin-bottom: 3px;
    }
    .active-doc-card .doc-name {
        font-size: 0.92rem;
        font-weight: 700;
        color: #1a1a2e;
        line-height: 1.3;
    }
    .active-doc-card .doc-meta {
        font-size: 0.75rem;
        color: #6b7280;
        margin-top: 2px;
    }
    /* analytics card */
    .analytics-btn-wrap {
        background: #fafafa;
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        padding: 8px 12px;
        margin-top: 4px;
        text-align: center;
        transition: background 0.15s;
    }
    .analytics-btn-wrap:hover { background: #f0f0f0; }
    .analytics-btn-wrap .analytics-label {
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #999;
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Session state initialization
# ─────────────────────────────────────────────────────────────────────────────


def init_session_state():
    defaults = {
        "workflow": None,
        "case_state": None,
        "executor": None,
        "training_scenario": None,
        "training_score": 0,
        "training_total": 0,
        "training_step_index": 0,
        "training_answers": [],
        "training_history": _load_training_history(),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        "edit_mode": False,
        "cases_history": _load_cases_history(),
        "_just_parsed": False,
        "pending_auto_result": None,
        "editing_step_id": None,
        "step_configs": {},
        "case_input_config": {
            "type": "Client Profile",
            "fields": [
                {"name": "Name", "type": "Text"},
                {"name": "Date of Birth", "type": "Date"},
                {"name": "Address", "type": "Text"},
                {"name": "Citizenship", "type": "Text"},
                {"name": "Occupation", "type": "Text"},
                {"name": "Employer", "type": "Text"},
                {"name": "Account Type", "type": "Select"},
                {"name": "Source of Funds", "type": "Text"},
                {"name": "ID Document", "type": "Text"},
                {"name": "Notes", "type": "Text"},
            ],
        },
        "configs_saved": False,
        "_config_just_saved": False,
        "_saved_config_snapshot": None,
        "pipeline_step": 1,  # 1=Parse, 2=Configure, 3=Execute
        "active_exec_tab": "parse",  # parse | configure | execute
        "active_train_tab": "parse",  # parse | train
        "app_view": "home",  # home | execute | train
        "admin_mode": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_session_state()


# ─────────────────────────────────────────────────────────────────────────────
# Library — persistent local JSON store
# ─────────────────────────────────────────────────────────────────────────────

LIBRARY_PATH = DATA_DIR / "library.json"


def _load_library() -> list[dict]:
    """Load the SOP library from disk."""
    if LIBRARY_PATH.exists():
        try:
            return json.loads(LIBRARY_PATH.read_text())
        except json.JSONDecodeError:
            return []
    return []


def _save_library(library: list[dict]):
    """Persist the SOP library to disk."""
    LIBRARY_PATH.write_text(json.dumps(library, indent=2))


def save_workflow_to_library(wf: Workflow) -> str:
    """Save a workflow to the library. Returns the entry ID.
    If a workflow with the same name and source format already exists,
    it is replaced instead of creating a duplicate."""
    library = _load_library()

    # Check for existing entry with same name & source format
    existing = next(
        (
            e
            for e in library
            if e["name"] == wf.name and e.get("source_format") == wf.source_format
        ),
        None,
    )

    if existing:
        entry_id = existing["id"]
        existing.update(
            {
                "step_count": len(wf.steps),
                "saved_at": datetime.now().isoformat(),
                "workflow": wf.to_dict(),
            }
        )
    else:
        entry_id = uuid.uuid4().hex[:8]
        library.append(
            {
                "id": entry_id,
                "name": wf.name,
                "source_format": wf.source_format,
                "step_count": len(wf.steps),
                "saved_at": datetime.now().isoformat(),
                "workflow": wf.to_dict(),
            }
        )
    _save_library(library)
    return entry_id


def load_workflow_from_library(entry_id: str) -> Workflow | None:
    """Load a workflow from the library by entry ID."""
    library = _load_library()
    for entry in library:
        if entry["id"] == entry_id:
            return Workflow.from_dict(entry["workflow"])
    return None


def delete_from_library(entry_id: str):
    """Remove a workflow from the library."""
    library = _load_library()
    library = [e for e in library if e["id"] != entry_id]
    _save_library(library)


def _generate_default_configs(wf):
    """Generate pre-filled tool configs for each step in the workflow."""
    from engine.models import StepType

    configs = {}
    for sid, step in wf.steps.items():
        if step.step_type == StepType.START or step.step_type == StepType.END:
            configs[sid] = {
                "tool_type": "None",
                "description": step.description,
                "prompt_template": "",
                "input_fields": [],
                "output_fields": [],
            }
        elif step.step_type == StepType.AUTO:
            configs[sid] = {
                "tool_type": "AI Prompt",
                "description": step.description,
                "prompt_template": f"Analyze the client data and execute: {step.title}.\nConsider all relevant compliance requirements.\nReturn a JSON object with result, data_gathered, flags, and status fields.",
                "input_fields": ["client_data", "previous_results"],
                "output_fields": ["result", "data_gathered", "flags", "status"],
            }
        elif step.step_type == StepType.HUMAN:
            configs[sid] = {
                "tool_type": "Human Review",
                "description": step.description,
                "prompt_template": "",
                "input_fields": ["client_data", "previous_results", "flags"],
                "output_fields": ["decision", "action_taken", "notes"],
                "form_fields": [
                    "Action taken (text)",
                    "Notes (text)",
                    "Decision (select: Approved / Needs Follow-up / Rejected)",
                ],
            }
        elif step.step_type == StepType.DECISION:
            branches_str = (
                ", ".join(step.branches.keys()) if step.branches else "Yes, No"
            )
            configs[sid] = {
                "tool_type": "Decision Gate",
                "description": step.description,
                "prompt_template": f"Evaluate the condition: {step.title}.\nBased on previous step results and client data, determine the appropriate branch.\nOptions: {branches_str}",
                "input_fields": ["previous_results", "flags", "risk_level"],
                "output_fields": ["decision", "reasoning"],
            }
    return configs


# ─────────────────────────────────────────────────────────────────────────────
# Parse function  (defined before sidebar so the button callback can find it)
# ─────────────────────────────────────────────────────────────────────────────


def parse_sop(input_format, use_sample, uploaded_file, sop_text):
    """Parse the SOP based on selected format and input."""
    try:
        progress_bar = st.progress(0, text="Initializing parser...")
        format_label = {
            "Text SOP": "text",
            "BPMN (.bpmn)": "BPMN",
            "Visio (.vsdx)": "Visio",
        }[input_format]
        stages = [
            (0.15, f"Loading {format_label} document..."),
            (0.35, "Extracting structure and elements..."),
            (0.55, "Identifying steps and decision points..."),
            (0.75, "Mapping connections and branches..."),
            (0.90, "Building workflow graph..."),
        ]
        with st.spinner("Parsing document..."):
            if input_format == "Text SOP":
                if use_sample:
                    if st.session_state.api_key:
                        text = (DATA_DIR / "sample_sop.txt").read_text()
                        for pct, msg in stages[:2]:
                            progress_bar.progress(pct, text=msg)
                            time.sleep(0.3)
                        wf = parse_text_sop(text, st.session_state.api_key)
                    elif get_demo_workflow:
                        for pct, msg in stages:
                            progress_bar.progress(pct, text=msg)
                            time.sleep(0.4)
                        wf = get_demo_workflow()
                    else:
                        st.error(
                            "API key required to parse text SOPs. Add your key in the sidebar."
                        )
                        return
                elif uploaded_file:
                    text = uploaded_file.read().decode("utf-8")
                    wf = parse_text_sop(text, st.session_state.api_key)
                elif sop_text:
                    wf = parse_text_sop(sop_text, st.session_state.api_key)
                else:
                    st.error("Please upload a file or paste document text")
                    return

            elif input_format == "BPMN (.bpmn)":
                if use_sample:
                    for pct, msg in stages:
                        progress_bar.progress(pct, text=msg)
                        time.sleep(0.3)
                    wf = parse_bpmn(str(DATA_DIR / "sample_process.bpmn"))
                elif uploaded_file:
                    # Save temp file
                    tmp = DATA_DIR / "_uploaded.bpmn"
                    tmp.write_bytes(uploaded_file.read())
                    wf = parse_bpmn(str(tmp))
                    tmp.unlink()
                else:
                    st.error("Please upload a BPMN file")
                    return

            elif input_format == "Visio (.vsdx)":
                if use_sample:
                    for pct, msg in stages:
                        progress_bar.progress(pct, text=msg)
                        time.sleep(0.35)
                    vsdx_path = DATA_DIR / "sample_process.vsdx"
                    if not vsdx_path.exists():
                        st.error(
                            "Sample .vsdx not found. Run: `python tools/create_sample_visio.py`"
                        )
                        return
                    wf = parse_visio(str(vsdx_path))
                elif uploaded_file:
                    tmp = DATA_DIR / "_uploaded.vsdx"
                    tmp.write_bytes(uploaded_file.read())
                    wf = parse_visio(str(tmp))
                    tmp.unlink()
                else:
                    st.error("Please upload a Visio file")
                    return

            progress_bar.empty()
            st.session_state.workflow = wf
            st.session_state.case_state = None
            st.session_state.training_scenario = None
            st.session_state.step_configs = _generate_default_configs(wf)
            st.session_state.configs_saved = False
            st.session_state.pipeline_step = 1
            st.session_state._just_parsed = True
            # Auto-save to library
            entry_id = save_workflow_to_library(wf)
            st.session_state._last_saved_id = entry_id
            st.rerun()

    except Exception as e:
        st.error(f"Parse error: {e}")


# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# App-wide logo (always visible in toolbar, on every page)
# ─────────────────────────────────────────────────────────────────────────────
_LOGO_FULL_SVG = BASE_DIR / "assets" / "logo_full.svg"
st.logo(str(_LOGO_FULL_SVG), size="large")

# Sidebar  (placed after parse_sop so the callback resolves)
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:

    # ── Import / Parse ──
    st.markdown("### Import")
    input_format = st.selectbox(
        "Document type",
        ["Text (.txt)", "BPMN (.bpmn)", "Visio (.vsdx)"],
        label_visibility="collapsed",
        help="Choose the format of the SOP document you want to parse",
    )

    uploaded_file = None
    sop_text = None

    if input_format == "Text (.txt)":
        uploaded_file = st.file_uploader(
            "Upload .txt",
            type=["txt"],
            label_visibility="collapsed",
            help="Max 200 MB per file · Plain-text SOP documents",
        )
        sop_text = st.text_area(
            "Or paste text",
            height=90,
            label_visibility="collapsed",
            placeholder="Paste SOP text here…",
        )
    elif input_format == "BPMN (.bpmn)":
        uploaded_file = st.file_uploader(
            "Upload .bpmn",
            type=["bpmn", "xml"],
            label_visibility="collapsed",
            help="Max 200 MB · BPMN 2.0 or XML process files",
        )
    else:
        uploaded_file = st.file_uploader(
            "Upload .vsdx",
            type=["vsdx"],
            label_visibility="collapsed",
            help="Max 200 MB · Microsoft Visio flowcharts",
        )

    use_sample = False  # Hidden for demo

    if st.button(
        "Parse Document",
        type="primary",
        use_container_width=True,
        icon=":material/play_arrow:",
    ):
        fmt_map = {
            "Text (.txt)": "Text SOP",
            "BPMN (.bpmn)": "BPMN (.bpmn)",
            "Visio (.vsdx)": "Visio (.vsdx)",
        }
        parse_sop(fmt_map[input_format], use_sample, uploaded_file, sop_text)

    # ── Active document ──
    if st.session_state.workflow:
        wf = st.session_state.workflow
        stats = wf.get_stats()
        if st.session_state.get("_just_parsed"):
            st.toast(f"Parsed: {wf.name} — {stats['total_steps']} steps")
            st.session_state._just_parsed = False
        st.markdown(
            f"""<div class="active-doc-card">
                <div class="doc-label">Active document</div>
                <div class="doc-name">{wf.name}</div>
                <div class="doc-meta">{wf.source_format.upper()} · {stats['total_steps']} steps · {stats['decision_points']} decisions</div>
            </div>""",
            unsafe_allow_html=True,
        )

    st.divider()

    # ── Saved Documents ──
    library = _load_library()
    st.markdown("### Library")
    if not library:
        st.caption("No saved documents yet.")
    else:
        for entry in library:
            name = entry["name"]
            with st.container(border=True):
                if st.button(
                    name,
                    key=f"load_{entry['id']}",
                    use_container_width=True,
                    icon=":material/description:",
                ):
                    loaded_wf = load_workflow_from_library(entry["id"])
                    if loaded_wf:
                        st.session_state.workflow = loaded_wf
                        st.session_state.case_state = None
                        st.session_state.training_scenario = None
                        # Restore saved configs if they exist in library entry
                        _saved_cfgs = entry.get("step_configs")
                        _saved_ci = entry.get("case_input_config")
                        if _saved_ci:
                            st.session_state.case_input_config = _saved_ci
                        if _saved_cfgs:
                            st.session_state.step_configs = _saved_cfgs
                            st.session_state.configs_saved = True
                            st.session_state.pipeline_step = 2
                        else:
                            st.session_state.step_configs = _generate_default_configs(
                                loaded_wf
                            )
                            st.session_state.configs_saved = False
                            st.session_state.pipeline_step = 1
                        st.session_state._just_parsed = False
                        st.rerun()
                if st.button(
                    "Delete",
                    key=f"delete_{entry['id']}",
                    type="tertiary",
                    icon=":material/close:",
                ):
                    delete_from_library(entry["id"])
                    remaining = _load_library()
                    if not remaining:
                        st.session_state.workflow = None
                        st.session_state.case_state = None
                        st.session_state.executor = None
                        st.session_state.training_scenario = None
                        st.session_state.step_configs = {}
                        st.session_state.configs_saved = False
                        st.session_state.pipeline_step = 1
                    st.rerun()
        if st.button(
            "Clear all",
            key="clear_library",
            type="tertiary",
            icon=":material/delete_sweep:",
            use_container_width=True,
        ):
            for entry in library:
                delete_from_library(entry["id"])
            st.session_state.workflow = None
            st.session_state.case_state = None
            st.session_state.executor = None
            st.session_state.training_scenario = None
            st.session_state.step_configs = {}
            st.session_state.configs_saved = False
            st.session_state.pipeline_step = 1
            st.rerun()

    st.divider()

    # ── Settings row: API Key + Analytics ──
    _s1, _s2 = st.columns(2)
    with _s1:
        with st.popover(":material/key: API Key", use_container_width=True):
            api_key = st.text_input(
                "OpenAI API Key",
                value=st.session_state.api_key,
                type="password",
                label_visibility="collapsed",
                placeholder="OpenAI or Azure OpenAI key",
            )
            st.session_state.api_key = api_key
    with _s2:
        _adm_on = st.session_state.admin_mode
        if st.button(
            "Analytics" if not _adm_on else "Close",
            key="admin_toggle",
            type="primary" if _adm_on else "secondary",
            icon=":material/bar_chart:" if not _adm_on else ":material/close:",
            use_container_width=True,
        ):
            st.session_state.admin_mode = not _adm_on
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Graph visualization
# ─────────────────────────────────────────────────────────────────────────────


def render_workflow_graph(
    workflow: Workflow,
    current_step_id: str = None,
    completed: list = None,
) -> graphviz.Digraph:
    """Render the workflow as a polished Graphviz directed graph."""
    dot = graphviz.Digraph(comment=workflow.name)
    dot.attr(
        rankdir="TB",
        bgcolor="transparent",
        fontname="Inter, Helvetica, Arial, sans-serif",
        pad="0.4",
        nodesep="0.5",
        ranksep="0.6",
        splines="ortho",
    )
    dot.attr(
        "node",
        fontname="Inter, Helvetica, Arial, sans-serif",
        fontsize="11",
        margin="0.2,0.12",
    )
    dot.attr(
        "edge",
        fontname="Inter, Helvetica, Arial, sans-serif",
        fontsize="9",
        arrowsize="0.7",
    )

    completed = completed or []

    type_styles = {
        StepType.START: {
            "shape": "circle",
            "color": "#22C55E",
            "fillcolor": "#22C55E",
            "fontcolor": "white",
            "width": "0.6",
            "height": "0.6",
            "fixedsize": "true",
        },
        StepType.END: {
            "shape": "doublecircle",
            "color": "#EF4444",
            "fillcolor": "#EF4444",
            "fontcolor": "white",
            "width": "0.6",
            "height": "0.6",
            "fixedsize": "true",
        },
        StepType.AUTO: {
            "shape": "box",
            "color": "#3B82F6",
            "fillcolor": "#EFF6FF",
            "fontcolor": "#1E3A5F",
            "style": "filled,rounded",
        },
        StepType.HUMAN: {
            "shape": "box",
            "color": "#8B5CF6",
            "fillcolor": "#F5F3FF",
            "fontcolor": "#3B1F7E",
            "style": "filled,rounded",
        },
        StepType.DECISION: {
            "shape": "diamond",
            "color": "#F59E0B",
            "fillcolor": "#FFFBEB",
            "fontcolor": "#78350F",
        },
    }

    for step_id, step in workflow.steps.items():
        style_cfg = type_styles.get(step.step_type, type_styles[StepType.HUMAN])

        # Label — short for start/end, detailed for others
        if step.step_type == StepType.START:
            label = "Start"
        elif step.step_type == StepType.END:
            label = "End"
        else:
            # Wrap long titles
            title = step.title
            if len(title) > 28:
                words = title.split()
                lines, cur = [], ""
                for w in words:
                    if cur and len(cur) + 1 + len(w) > 28:
                        lines.append(cur)
                        cur = w
                    else:
                        cur = f"{cur} {w}" if cur else w
                if cur:
                    lines.append(cur)
                title = "\\n".join(lines)
            type_tag = {"AUTO": "AI", "HUMAN": "Manual", "DECISION": "Decision"}.get(
                step.step_type.value, step.step_type.value
            )
            label = f"{title}\\n\\n[{type_tag}]"

        # Highlight states
        if step_id == current_step_id:
            fillcolor = "#FEF3C7"
            fontcolor = "#92400E"
            penwidth = "2.5"
            color = "#F59E0B"
            node_style = style_cfg.get("style", "filled") + ",bold"
        elif step_id in completed:
            fillcolor = "#DCFCE7"
            fontcolor = "#166534"
            penwidth = "1.5"
            color = "#22C55E"
            node_style = style_cfg.get("style", "filled")
        else:
            fillcolor = style_cfg.get("fillcolor", style_cfg["color"])
            fontcolor = style_cfg["fontcolor"]
            penwidth = "1.2"
            color = style_cfg["color"]
            node_style = style_cfg.get("style", "filled")

        node_kwargs = dict(
            label=label,
            shape=style_cfg["shape"],
            style=node_style,
            fillcolor=fillcolor,
            fontcolor=fontcolor,
            color=color,
            penwidth=penwidth,
        )
        # Fixed size for start/end circles
        if "width" in style_cfg:
            node_kwargs["width"] = style_cfg["width"]
            node_kwargs["height"] = style_cfg["height"]
            node_kwargs["fixedsize"] = style_cfg["fixedsize"]

        dot.node(step_id, **node_kwargs)

    # Edges — clean arrows
    for step_id, step in workflow.steps.items():
        for next_id in step.next_steps:
            if next_id in workflow.steps:
                dot.edge(step_id, next_id, color="#94A3B8", arrowhead="vee")
        for label, target_id in step.branches.items():
            if target_id in workflow.steps:
                dot.edge(
                    step_id,
                    target_id,
                    label=f"  {label}  ",
                    color="#94A3B8",
                    fontcolor="#64748B",
                    arrowhead="vee",
                    style="dashed",
                )

    return dot


# ─────────────────────────────────────────────────────────────────────────────
# Tab: PARSE
# ─────────────────────────────────────────────────────────────────────────────


def render_parse_tab():
    """Show the parsed workflow graph and step details."""
    wf = st.session_state.workflow
    if not wf:
        st.info("Parse a document from the sidebar to view the workflow here.")
        return

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("Workflow Graph")
        dot = render_workflow_graph(wf)
        st.graphviz_chart(dot, width="stretch")

    with col2:
        st.subheader("Workflow Details")
        stats = wf.get_stats()

        # Metrics row
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Steps", stats["total_steps"])
        m2.metric("Decisions", stats["decision_points"])
        m3.metric("Owners", len(stats["owners"]))

        st.caption(f"**Source format:** {wf.source_format}")
        st.caption(f"**Owners:** {', '.join(stats['owners'])}")

        # Step breakdown
        st.divider()
        type_labels = {
            "AUTO": "Auto",
            "HUMAN": "Human",
            "DECISION": "Decision",
            "START": "Start",
            "END": "End",
        }
        import pandas as pd

        step_type_df = pd.DataFrame(
            [
                {"Type": type_labels.get(tc, tc), "Count": count}
                for tc, count in stats["type_counts"].items()
            ]
        )
        st.dataframe(step_type_df, hide_index=True, width="stretch")

        # ── Export Workflow JSON ──
        st.divider()
        wf_json = json.dumps(wf.to_dict(), indent=2)
        st.download_button(
            "Export Workflow (JSON)",
            data=wf_json,
            file_name=f"workflow_{wf.source_format}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            width="stretch",
        )

    # ── Inline Workflow Editor ──
    st.divider()
    edit_col1, edit_col2 = st.columns([6, 1])
    with edit_col1:
        st.subheader(
            "Workflow Steps" + (" — Edit Mode" if st.session_state.edit_mode else "")
        )
    with edit_col2:
        if st.button(
            "Edit" if not st.session_state.edit_mode else "Done",
            width="stretch",
        ):
            st.session_state.edit_mode = not st.session_state.edit_mode
            st.rerun()

    type_options = [t.value for t in StepType]
    all_step_ids = list(wf.steps.keys())
    step_label_map = {sid: wf.steps[sid].title for sid in all_step_ids}
    type_labels = {
        "AUTO": "Auto",
        "HUMAN": "Human",
        "DECISION": "Decision",
        "START": "Start",
        "END": "End",
    }

    for step in list(wf.steps.values()):
        step_label = type_labels.get(step.step_type.value, step.step_type.value)

        if st.session_state.edit_mode:
            with st.expander(
                f"{step_label}: {step.title} ({step.step_type.value})", expanded=False
            ):
                c1, c2 = st.columns(2)
                with c1:
                    new_title = st.text_input(
                        "Title", value=step.title, key=f"edit_title_{step.id}"
                    )
                    new_type = st.selectbox(
                        "Type",
                        type_options,
                        index=type_options.index(step.step_type.value),
                        key=f"edit_type_{step.id}",
                    )
                with c2:
                    new_owner = st.text_input(
                        "Owner", value=step.owner, key=f"edit_owner_{step.id}"
                    )
                    new_desc = st.text_area(
                        "Description",
                        value=step.description,
                        key=f"edit_desc_{step.id}",
                        height=80,
                    )

                # Apply edits live
                if new_title != step.title:
                    step.title = new_title
                if new_type != step.step_type.value:
                    step.step_type = StepType(new_type)
                    # Auto-regenerate config for this step to match new type
                    if st.session_state.step_configs:
                        single = _generate_default_configs(
                            type("_W", (), {"steps": {step.id: step}})()
                        )
                        st.session_state.step_configs[step.id] = single.get(step.id, {})
                        st.session_state.configs_saved = False
                        st.toast(
                            f'Config for "{step.title}" updated to match new type: {new_type}',
                            icon=":material/sync:",
                        )
                if new_owner != step.owner:
                    step.owner = new_owner
                if new_desc != step.description:
                    step.description = new_desc

                st.divider()

                # ── Connections (next_steps) ──
                st.markdown("**Connections**")
                other_ids = [s for s in all_step_ids if s != step.id]
                other_labels = [step_label_map.get(s, s) for s in other_ids]
                current_next = [s for s in step.next_steps if s in wf.steps]
                current_next_idx = [
                    other_ids.index(s) for s in current_next if s in other_ids
                ]
                selected_next = st.multiselect(
                    "Next steps",
                    options=range(len(other_ids)),
                    default=current_next_idx,
                    format_func=lambda i: other_labels[i],
                    key=f"edit_next_{step.id}",
                )
                step.next_steps = [other_ids[i] for i in selected_next]

                # ── Branches ──
                st.markdown("**Branches** (for DECISION steps)")
                # Show existing branches with delete
                branches_to_delete = []
                for label, tid in list(step.branches.items()):
                    tname = step_label_map.get(tid, tid)
                    bc1, bc2 = st.columns([5, 1])
                    bc1.caption(f"[{label}] → {tname}")
                    if bc2.button("×", key=f"del_branch_{step.id}_{label}"):
                        branches_to_delete.append(label)
                for bl in branches_to_delete:
                    del step.branches[bl]
                    st.rerun()

                # Add new branch
                with st.popover("➕ Add Branch"):
                    new_label = st.text_input(
                        "Branch label (e.g. Yes / No)",
                        key=f"new_branch_label_{step.id}",
                    )
                    target_idx = st.selectbox(
                        "Target step",
                        range(len(other_ids)),
                        format_func=lambda i: other_labels[i],
                        key=f"new_branch_target_{step.id}",
                    )
                    if st.button("Add", key=f"add_branch_btn_{step.id}"):
                        if new_label and target_idx is not None:
                            step.branches[new_label] = other_ids[target_idx]
                            st.rerun()

                # ── Insert step after / Delete step ──
                st.divider()
                ins_col, del_col = st.columns(2)
                with ins_col:
                    with st.popover("➕ Insert After", width="stretch"):
                        ins_title = st.text_input("Title", key=f"ins_title_{step.id}")
                        ic1, ic2 = st.columns(2)
                        with ic1:
                            ins_type = st.selectbox(
                                "Type", type_options, key=f"ins_type_{step.id}"
                            )
                            ins_owner = st.text_input(
                                "Owner", value="System", key=f"ins_owner_{step.id}"
                            )
                        with ic2:
                            ins_desc = st.text_area(
                                "Description", key=f"ins_desc_{step.id}", height=80
                            )
                        if st.button(
                            "Insert", key=f"ins_btn_{step.id}", type="primary"
                        ):
                            if ins_title:
                                new_id = f"step_{uuid.uuid4().hex[:8]}"
                                new_step = Step(
                                    id=new_id,
                                    title=ins_title,
                                    description=ins_desc,
                                    step_type=StepType(ins_type),
                                    owner=ins_owner,
                                    next_steps=list(
                                        step.next_steps
                                    ),  # inherit outgoing connections
                                )
                                wf.steps[new_id] = new_step
                                # Point current step to the new step only
                                step.next_steps = [new_id]
                                # Also update branches that pointed forward
                                # (keep branches as-is; user can adjust)
                                st.rerun()
                with del_col:
                    if st.button(
                        "Delete",
                        key=f"del_step_{step.id}",
                        type="secondary",
                        width="stretch",
                    ):
                        # Remove from other steps' references
                        for other in wf.steps.values():
                            if step.id in other.next_steps:
                                other.next_steps.remove(step.id)
                            other.branches = {
                                k: v for k, v in other.branches.items() if v != step.id
                            }
                        del wf.steps[step.id]
                        if wf.start_step_id == step.id:
                            wf.start_step_id = next(iter(wf.steps), None)
                        st.rerun()
        else:
            with st.expander(f"{step_label}: {step.title} ({step.step_type.value})"):
                st.write(f"**Owner:** {step.owner}")
                st.write(f"**Description:** {step.description}")
                if step.next_steps:
                    targets = [
                        wf.steps[s].title for s in step.next_steps if s in wf.steps
                    ]
                    st.write(f"**Next:** {', '.join(targets)}")
                if step.branches:
                    for label, target_id in step.branches.items():
                        target_name = (
                            wf.steps[target_id].title
                            if target_id in wf.steps
                            else target_id
                        )
                        st.write(f"**Branch [{label}]:** {target_name}")

    # ── Add New Step ──
    if st.session_state.edit_mode:
        st.divider()
        with st.popover("➕ Add New Step", width="stretch"):
            new_step_title = st.text_input("Step title", key="new_step_title")
            ns1, ns2 = st.columns(2)
            with ns1:
                new_step_type = st.selectbox("Type", type_options, key="new_step_type")
                new_step_owner = st.text_input(
                    "Owner", value="System", key="new_step_owner"
                )
            with ns2:
                new_step_desc = st.text_area(
                    "Description", key="new_step_desc", height=80
                )
            if st.button("Create Step", key="create_step_btn", type="primary"):
                if new_step_title:
                    new_id = f"step_{uuid.uuid4().hex[:8]}"
                    new_step = Step(
                        id=new_id,
                        title=new_step_title,
                        description=new_step_desc,
                        step_type=StepType(new_step_type),
                        owner=new_step_owner,
                    )
                    wf.steps[new_id] = new_step
                    st.rerun()

    # (navigation handled by top tab buttons)


# ─────────────────────────────────────────────────────────────────────────────
# Tab: EXECUTE
# ─────────────────────────────────────────────────────────────────────────────


def render_configure_tab():
    """Configure tool integrations for each workflow step."""
    wf = st.session_state.workflow
    if not wf:
        st.markdown(
            '<div class="empty-state">'
            "<h3>Configure Tools</h3>"
            "<p>Parse or load a document first, then configure tool integrations for each step.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Generate configs if missing (e.g. old session) ──
    if not st.session_state.step_configs:
        st.session_state.step_configs = _generate_default_configs(wf)

    # ── Shortcut: Use existing configuration? ──
    if st.session_state.get("_config_just_saved", False):
        st.session_state._config_just_saved = False
    elif st.session_state.configs_saved:
        st.markdown(
            """<style>
        /* Make the Yes button match the info-box height */
        [data-testid="stButton"]:has(button[key="skip_to_exec"]) button,
        button[kind="primary"][key="skip_to_exec"] {
            min-height: 54px !important;
            height: 100% !important;
        }
        </style>""",
            unsafe_allow_html=True,
        )
        _sc_l, _sc_r = st.columns([5, 1], vertical_alignment="center")
        with _sc_l:
            st.info("This workflow already has a saved configuration. Use it?")
        with _sc_r:
            if st.button(
                "Yes", type="primary", use_container_width=True, key="skip_to_exec"
            ):
                st.session_state.active_exec_tab = "execute"
                st.session_state.pipeline_step = 3
                st.rerun()

    st.subheader("Configuration")

    # ── Case Input Configuration ──
    st.markdown("##### Case Input")
    st.caption(
        "Define what input is needed when starting a new case for this workflow."
    )
    _ci = st.session_state.case_input_config
    _ci_options = ["Client Profile", "Application Form", "Transaction Record", "Custom"]
    _cur_ci = _ci.get("type", "Client Profile")
    if _cur_ci not in _ci_options:
        _ci_options.append(_cur_ci)
    _ci_idx = _ci_options.index(_cur_ci) if _cur_ci in _ci_options else 0
    new_ci_type = st.selectbox(
        "Case Input Type", _ci_options, index=_ci_idx, key="case_input_type_sel"
    )
    st.session_state.case_input_config["type"] = new_ci_type

    # ── Editable schema fields with data types ──
    _default_schemas = {
        "Client Profile": [
            {"name": "Name", "type": "Text"},
            {"name": "Date of Birth", "type": "Date"},
            {"name": "Address", "type": "Text"},
            {"name": "Citizenship", "type": "Text"},
            {"name": "Occupation", "type": "Text"},
            {"name": "Employer", "type": "Text"},
            {"name": "Account Type", "type": "Select"},
            {"name": "Source of Funds", "type": "Text"},
            {"name": "ID Document", "type": "Text"},
            {"name": "Notes", "type": "Text"},
        ],
        "Application Form": [
            {"name": "Applicant Name", "type": "Text"},
            {"name": "Application ID", "type": "Text"},
            {"name": "Date Submitted", "type": "Date"},
            {"name": "Category", "type": "Select"},
            {"name": "Status", "type": "Select"},
            {"name": "Notes", "type": "Text"},
        ],
        "Transaction Record": [
            {"name": "Transaction ID", "type": "Text"},
            {"name": "Date", "type": "Date"},
            {"name": "Amount", "type": "Number"},
            {"name": "Sender", "type": "Text"},
            {"name": "Receiver", "type": "Text"},
            {"name": "Type", "type": "Select"},
            {"name": "Notes", "type": "Text"},
        ],
        "Custom": [
            {"name": "Field 1", "type": "Text"},
            {"name": "Field 2", "type": "Text"},
            {"name": "Field 3", "type": "Text"},
        ],
    }
    _data_type_options = ["Text", "Number", "Date", "Email", "Select"]

    # Migrate old list-of-strings format to list-of-dicts
    _existing_fields = _ci.get("fields", [])
    if _existing_fields and isinstance(_existing_fields[0], str):
        _existing_fields = [{"name": f, "type": "Text"} for f in _existing_fields]
        st.session_state.case_input_config["fields"] = _existing_fields

    if not _existing_fields or _ci.get("_last_type") != new_ci_type:
        _existing_fields = _default_schemas.get(
            new_ci_type, [{"name": "Field 1", "type": "Text"}]
        )
        st.session_state.case_input_config["_last_type"] = new_ci_type
        st.session_state.case_input_config["fields"] = _existing_fields

    st.markdown("**Schema Fields**")
    _updated_fields = []
    for _si, _sf in enumerate(_existing_fields):
        _fc1, _fc2, _fc3 = st.columns([3, 2, 0.5])
        with _fc1:
            _fn = st.text_input(
                "Field",
                value=_sf.get("name", ""),
                key=f"sf_name_{_si}",
                label_visibility="collapsed",
            )
        with _fc2:
            _ft_cur = _sf.get("type", "Text")
            _ft_idx = (
                _data_type_options.index(_ft_cur)
                if _ft_cur in _data_type_options
                else 0
            )
            _ft = st.selectbox(
                "Type",
                _data_type_options,
                index=_ft_idx,
                key=f"sf_type_{_si}",
                label_visibility="collapsed",
            )
        with _fc3:
            _remove = st.button("\u2715", key=f"sf_del_{_si}", type="tertiary")
        if not _remove and _fn.strip():
            _updated_fields.append({"name": _fn.strip(), "type": _ft})

    # Add field button
    if st.button("+ Add Field", key="add_schema_field", type="tertiary"):
        _updated_fields.append(
            {"name": f"Field {len(_updated_fields) + 1}", "type": "Text"}
        )

    st.session_state.case_input_config["fields"] = _updated_fields
    st.divider()

    st.caption(
        "Each step has a pre-filled tool configuration. "
        "In production, these would connect to real APIs, databases, and services. "
        "For this demo, AI steps use GPT-4o and human steps collect input via forms."
    )

    configs = st.session_state.step_configs
    tool_type_options = [
        "AI Prompt",
        "API Call",
        "Database Query",
        "Script",
        "Human Review",
        "Decision Gate",
        "None",
    ]
    type_css = {
        "AUTO": "cfg-type-auto",
        "HUMAN": "cfg-type-human",
        "DECISION": "cfg-type-decision",
        "START": "cfg-type-start",
        "END": "cfg-type-end",
    }

    ordered_steps = list(wf.steps.values())

    for step in ordered_steps:
        cfg = configs.get(step.id, {})
        stype = step.step_type.value
        badge_cls = type_css.get(stype, "cfg-type-auto")

        # Skip START/END — just show them as info
        if step.step_type in (StepType.START, StepType.END):
            st.markdown(
                f'<div class="cfg-card">'
                f'<div class="cfg-card-header">'
                f'<span class="cfg-type-badge {badge_cls}">{stype}</span>'
                f"<strong>{step.title}</strong>"
                f"</div>"
                f'<p style="margin:0; color:#6B6B6B; font-size:0.85rem;">{step.description or "No configuration needed."}</p>'
                f"</div>",
                unsafe_allow_html=True,
            )
            continue

        with st.expander(f"{step.title}  —  {stype}", expanded=False):
            col_type, col_status = st.columns([3, 1])
            with col_type:
                cur_tool = cfg.get("tool_type", "AI Prompt")
                idx = (
                    tool_type_options.index(cur_tool)
                    if cur_tool in tool_type_options
                    else 0
                )
                new_tool = st.selectbox(
                    "Tool Type",
                    tool_type_options,
                    index=idx,
                    key=f"cfg_tool_{step.id}",
                )
                configs[step.id]["tool_type"] = new_tool
            with col_status:
                st.markdown(
                    f'<div style="margin-top:28px;">'
                    f'<span class="cfg-type-badge {badge_cls}">{stype}</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # ── Guidance callout per tool type ──
            _guidance = {
                "AI Prompt": (
                    "info",
                    "**AI Prompt** — This step runs automatically via GPT-4o. "
                    "Provide a prompt template below. The system will inject client data "
                    "and previous step results, then return structured JSON output.",
                ),
                "Human Review": (
                    "warning",
                    "**Human Review** — This step pauses execution for a human operator. "
                    "During execution, the operator will see a form with the fields listed below "
                    "and must provide: an action taken, any notes, and a decision (Approved / Needs Follow-up / Rejected).",
                ),
                "Decision Gate": (
                    "info",
                    "**Decision Gate** — AI evaluates a condition and chooses a branch. "
                    "Provide a prompt template. The system will return a decision and reasoning, "
                    "then route to the matching branch.",
                ),
                "API Call": (
                    "info",
                    "**API Call** — In production this would call an external API. "
                    "For the demo, this behaves like an AI Prompt step.",
                ),
                "Database Query": (
                    "info",
                    "**Database Query** — In production this would query a database. "
                    "For the demo, this behaves like an AI Prompt step.",
                ),
                "Script": (
                    "info",
                    "**Script** — In production this would execute a script. "
                    "For the demo, this behaves like an AI Prompt step.",
                ),
                "None": (
                    "info",
                    "**No Tool** — This step has no tool integration (e.g. start/end markers).",
                ),
            }
            _g_type, _g_msg = _guidance.get(new_tool, ("info", ""))
            if _g_msg:
                getattr(st, _g_type)(_g_msg)

            # Prompt template (for AI Prompt / Decision Gate)
            if new_tool in ("AI Prompt", "Decision Gate"):
                prompt = st.text_area(
                    "Prompt Template",
                    value=cfg.get("prompt_template", ""),
                    height=80,
                    key=f"cfg_prompt_{step.id}",
                )
                configs[step.id]["prompt_template"] = prompt

            # Input/Output mapping
            inp_col, out_col = st.columns(2)
            with inp_col:
                inputs_str = ", ".join(cfg.get("input_fields", []))
                new_inputs = st.text_input(
                    "Input Fields",
                    value=inputs_str,
                    key=f"cfg_in_{step.id}",
                    help="Comma-separated field names",
                )
                configs[step.id]["input_fields"] = [
                    x.strip() for x in new_inputs.split(",") if x.strip()
                ]
            with out_col:
                outputs_str = ", ".join(cfg.get("output_fields", []))
                new_outputs = st.text_input(
                    "Output Fields",
                    value=outputs_str,
                    key=f"cfg_out_{step.id}",
                    help="Comma-separated field names",
                )
                configs[step.id]["output_fields"] = [
                    x.strip() for x in new_outputs.split(",") if x.strip()
                ]

            # Human Review: show form fields
            if new_tool == "Human Review":
                form_fields = cfg.get("form_fields", [])
                if not form_fields:
                    form_fields = [
                        "Action taken (text)",
                        "Notes (text)",
                        "Decision (select: Approved / Needs Follow-up / Rejected)",
                    ]
                    configs[step.id]["form_fields"] = form_fields
                st.markdown(
                    "**Form fields presented to the operator during execution:**"
                )
                for _ff in form_fields:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;• {_ff}")

            # Description
            st.markdown(
                f"<p style='margin:4px 0 0 0; color:#6B6B6B; font-size:0.8rem;'>{step.description}</p>",
                unsafe_allow_html=True,
            )

    st.session_state.step_configs = configs

    # ── Detect config edits after save ──
    if st.session_state.configs_saved and st.session_state.get(
        "_saved_config_snapshot"
    ):
        import json as _json

        _current_snap = _json.dumps(
            {
                "step_configs": st.session_state.step_configs,
                "case_input_config": st.session_state.case_input_config,
            },
            sort_keys=True,
        )
        if _current_snap != st.session_state._saved_config_snapshot:
            st.session_state.configs_saved = False
            st.session_state._saved_config_snapshot = None

    # ── Save Configuration ──
    st.divider()
    save_col, info_col = st.columns([1, 2])
    with save_col:
        if st.button(
            "Save Configuration",
            type="primary",
            icon=":material/save:",
            width="stretch",
        ):
            st.session_state.configs_saved = True
            st.session_state._config_just_saved = True
            # Snapshot current config so we can detect edits later
            import json as _json

            st.session_state._saved_config_snapshot = _json.dumps(
                {
                    "step_configs": st.session_state.step_configs,
                    "case_input_config": st.session_state.case_input_config,
                },
                sort_keys=True,
            )
            st.session_state.pipeline_step = max(st.session_state.pipeline_step, 2)
            st.session_state.active_exec_tab = (
                "configure"  # stay on configure after save
            )
            # Persist configs to library so they survive reload
            _wf = st.session_state.workflow
            if _wf:
                _lib = _load_library()
                for _entry in _lib:
                    if (
                        _entry["name"] == _wf.name
                        and _entry.get("source_format") == _wf.source_format
                    ):
                        _entry["step_configs"] = st.session_state.step_configs
                        _entry["case_input_config"] = st.session_state.case_input_config
                        break
                _save_library(_lib)
            st.toast(
                "Configuration saved! You can now execute workflows.",
                icon=":material/check_circle:",
            )
            st.rerun()
    with info_col:
        if st.session_state.configs_saved:
            st.success(
                "Configuration saved. Switch to the **Execute** tab to run cases.",
                icon=":material/check_circle:",
            )
        else:
            st.info(
                "Review the configuration and click **Save Configuration** to proceed."
            )


def render_execute_tab():
    """Execute a workflow case step-by-step."""
    wf = st.session_state.workflow
    if not wf:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No Workflow to Execute</h3>"
            "<p>Parse or load a document first, then come back to run cases.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    if not st.session_state.configs_saved:
        st.markdown(
            '<div class="empty-state">'
            "<h3>Configuration Required</h3>"
            "<p>Go to <strong>2. Configure</strong> and save your configuration before executing.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # ── Case Input ──
    _ci_cfg = st.session_state.case_input_config
    _ci_type = _ci_cfg.get("type", "Client Profile")
    _ci_fields = _ci_cfg.get("fields", ["Name", "Notes"])
    st.subheader(f"{_ci_type}")

    _input_modes = ["Select from list", "Create new", "Upload file"]
    _input_mode = st.radio(
        "Input Method",
        _input_modes,
        horizontal=True,
        key="case_input_mode",
        label_visibility="collapsed",
    )

    selected_case_input = None

    if _input_mode == "Select from list":
        if _ci_type == "Client Profile":
            _clients_path = DATA_DIR / "clients.json"
            clients = json.loads(_clients_path.read_text())
            if not clients:
                st.info("No client profiles saved yet. Use **Create new** to add one.")
            else:
                client_names = [c["name"] for c in clients]
                _sel_col, _del_col = st.columns([5, 1], vertical_alignment="bottom")
                with _sel_col:
                    selected_idx = st.selectbox(
                        _ci_type,
                        range(len(clients)),
                        format_func=lambda i: client_names[i],
                    )
                with _del_col:
                    if st.button(
                        "Remove",
                        key="remove_client_btn",
                        type="tertiary",
                        icon=":material/delete:",
                        use_container_width=True,
                    ):
                        _removed = clients.pop(selected_idx)
                        _clients_path.write_text(json.dumps(clients, indent=2))
                        st.toast(
                            f"Removed **{_removed.get('name', 'entry')}** from list.",
                            icon=":material/delete:",
                        )
                        st.rerun()
                selected_case_input = clients[selected_idx]
        else:
            st.info(
                f"No pre-loaded {_ci_type.lower()} records available. Use **Create new** or **Upload file** instead."
            )

    elif _input_mode == "Create new":
        st.caption(f"Fill in the {_ci_type.lower()} fields below.")
        _new_entry = {}
        _validation_errors = []

        # Migrate old list-of-strings schema to list-of-dicts
        if _ci_fields and isinstance(_ci_fields[0], str):
            _ci_fields = [{"name": f, "type": "Text"} for f in _ci_fields]

        # Build form from schema fields with typed inputs
        _form_cols = st.columns(2)
        for _fi, _field_def in enumerate(_ci_fields):
            _field_name = (
                _field_def
                if isinstance(_field_def, str)
                else _field_def.get("name", f"Field {_fi+1}")
            )
            _field_type = (
                "Text"
                if isinstance(_field_def, str)
                else _field_def.get("type", "Text")
            )
            _field_key = _field_name.lower().replace(" ", "_")

            with _form_cols[_fi % 2]:
                if _field_type == "Date":
                    _val = st.date_input(
                        _field_name, value=None, key=f"new_ci_{_fi}_{_field_name}"
                    )
                    _new_entry[_field_key] = str(_val) if _val else ""
                elif _field_type == "Number":
                    _val = st.number_input(
                        _field_name,
                        value=None,
                        key=f"new_ci_{_fi}_{_field_name}",
                        step=1.0,
                    )
                    _new_entry[_field_key] = _val if _val is not None else ""
                elif _field_type == "Email":
                    _val = st.text_input(
                        _field_name,
                        key=f"new_ci_{_fi}_{_field_name}",
                        placeholder="email@example.com",
                    )
                    _new_entry[_field_key] = _val
                    if _val and "@" not in _val:
                        _validation_errors.append(
                            f"{_field_name} must be a valid email address."
                        )
                elif _field_type == "Select":
                    _val = st.text_input(
                        _field_name,
                        key=f"new_ci_{_fi}_{_field_name}",
                        help="Enter value",
                    )
                    _new_entry[_field_key] = _val
                else:
                    _val = st.text_input(_field_name, key=f"new_ci_{_fi}_{_field_name}")
                    _new_entry[_field_key] = _val

        if _validation_errors:
            for _ve in _validation_errors:
                st.warning(_ve)

        # Set "name" from first field if not already present
        if _ci_fields:
            _first_name = (
                _ci_fields[0]
                if isinstance(_ci_fields[0], str)
                else _ci_fields[0].get("name", "")
            )
            _first_key = _first_name.lower().replace(" ", "_")
            if "name" not in _new_entry:
                _new_entry["name"] = str(_new_entry.get(_first_key, ""))
        _new_entry["type"] = _ci_type

        # Only valid if first field filled and no validation errors
        _first_name = (
            _ci_fields[0]
            if isinstance(_ci_fields[0], str)
            else _ci_fields[0].get("name", "") if _ci_fields else "name"
        )
        _first_key = _first_name.lower().replace(" ", "_")
        if _new_entry.get(_first_key) and not _validation_errors:
            selected_case_input = _new_entry

        # Save to list button (always visible)
        _save_disabled = not _new_entry.get(_first_key) or bool(_validation_errors)
        if st.button(
            "Save to list",
            key="save_new_to_list",
            icon=":material/save:",
            disabled=_save_disabled,
        ):
            _clients_path = DATA_DIR / "clients.json"
            _clients = (
                json.loads(_clients_path.read_text()) if _clients_path.exists() else []
            )
            _new_entry["id"] = f"entry_{uuid.uuid4().hex[:6]}"
            _clients.append(_new_entry)
            _clients_path.write_text(json.dumps(_clients, indent=2))
            st.success(
                f"Saved **{_new_entry.get('name', 'entry')}** to the list.",
                icon=":material/check_circle:",
            )

    else:
        _uploaded = st.file_uploader(
            f"Upload {_ci_type}",
            type=["json", "csv", "txt"],
            key="case_input_file",
        )
        if _uploaded:
            _raw = _uploaded.read().decode("utf-8", errors="replace")
            try:
                _parsed = json.loads(_raw)
                if isinstance(_parsed, list) and _parsed:
                    _parsed = _parsed[0]
                selected_case_input = _parsed
                st.success(f"Loaded {_ci_type} from {_uploaded.name}")
            except json.JSONDecodeError:
                selected_case_input = {
                    "name": _raw[:50],
                    "details": _raw,
                    "type": _ci_type,
                }
                st.success(f"Loaded text data from {_uploaded.name}")

    # Start / Reset case
    col_start, col_reset = st.columns(2)
    with col_start:
        _can_start = selected_case_input is not None
        if st.button(
            "Start Case", type="primary", width="stretch", disabled=not _can_start
        ):
            executor = WorkflowExecutor(wf, st.session_state.api_key or None)
            state = executor.start_case(
                case_id=str(uuid.uuid4())[:8],
                client_data=selected_case_input,
            )
            st.session_state.case_state = state
            st.session_state.executor = executor
            st.session_state.pipeline_step = 3
            st.rerun()

    with col_reset:
        if st.button("Reset", type="primary", width="stretch"):
            st.session_state.case_state = None
            st.session_state.executor = None
            st.session_state.pending_auto_result = None
            st.session_state.editing_step_id = None
            st.rerun()

    st.divider()

    # Show execution state
    state = st.session_state.case_state
    executor = st.session_state.executor

    if not state or not executor:
        st.markdown(
            '<div class="empty-state" style="padding:32px;">'
            "<h3>Ready to Execute</h3>"
            "<p>Select or upload a case input above and click <strong>Start Case</strong> to begin the workflow.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Show completed cases ──
        history = st.session_state.cases_history
        if history:
            st.divider()
            st.markdown("#### Cases")
            wf = st.session_state.workflow
            for idx, case in enumerate(reversed(history)):
                real_idx = len(history) - 1 - idx  # index in the actual list
                ts = case.get("timestamp", "")[:16].replace("T", " at ")
                case_status = case.get("status", "completed")
                status_tag = (
                    "Incomplete" if case_status == "incomplete" else "Completed"
                )
                label = f"{case.get('client_name', 'Unknown')} — {status_tag} — {case.get('steps_completed', 0)} steps  |  {ts}"

                with st.expander(label, expanded=False):
                    # ── Audit trail (if we have full state data) ──
                    completed_steps = case.get("completed_steps", [])
                    step_results = case.get("step_results", {})
                    decisions_made = case.get("decisions_made", {})

                    if completed_steps and wf:
                        for i, step_id in enumerate(completed_steps):
                            step = wf.steps.get(step_id)
                            result = step_results.get(step_id, {})
                            if step:
                                type_icon = {
                                    "START": "\u25b6",
                                    "END": "\u25a0",
                                    "AUTO": "\u2699",
                                    "HUMAN": "\U0001f464",
                                    "DECISION": "\u25c7",
                                }.get(step.step_type.value, "\u2022")
                                st.markdown(f"**{type_icon} {i+1}. {step.title}**")
                                if step_id in decisions_made:
                                    st.markdown(
                                        f"\u21b3 Decision: **{decisions_made[step_id]}**"
                                    )
                                if result:
                                    result_text = result.get(
                                        "result", result.get("action", "")
                                    )
                                    notes = result.get("notes", "")
                                    if result_text:
                                        st.caption(f"**Result:** {result_text}")
                                    if notes:
                                        st.caption(f"**Notes:** {notes}")
                                st.divider()
                    else:
                        st.caption(
                            f"Case ID: {case.get('case_id', '?')}  |  {case.get('decisions', 0)} decisions"
                        )

                    # ── Action buttons ──
                    btn_cols = st.columns(3)
                    with btn_cols[0]:
                        # Export CSV
                        if completed_steps and wf:
                            tmp_state = CaseState(
                                case_id=case["case_id"],
                                client_data=case.get("client_data", {}),
                                current_step_id=case.get("current_step_id", ""),
                                completed_steps=completed_steps,
                                decisions_made=decisions_made,
                                step_results=step_results,
                                status="completed",
                            )
                            csv_data = _generate_audit_csv(tmp_state, wf)
                            st.download_button(
                                "Export CSV",
                                data=csv_data,
                                file_name=f"audit_{case['case_id']}.csv",
                                mime="text/csv",
                                key=f"dl_{real_idx}",
                                use_container_width=True,
                            )
                    with btn_cols[1]:
                        # Reload for editing
                        if completed_steps and wf:
                            btn_label = (
                                "Resume"
                                if case.get("status") == "incomplete"
                                else "Reload & Edit"
                            )
                            if st.button(
                                btn_label,
                                key=f"reload_{real_idx}",
                                use_container_width=True,
                            ):
                                reloaded = CaseState(
                                    case_id=case["case_id"],
                                    client_data=case.get("client_data", {}),
                                    current_step_id=case.get("current_step_id", ""),
                                    completed_steps=list(completed_steps),
                                    decisions_made=dict(decisions_made),
                                    step_results=dict(step_results),
                                    status=case.get("status", "completed"),
                                )
                                if reloaded.status == "incomplete":
                                    reloaded.status = "in_progress"
                                executor = WorkflowExecutor(
                                    wf, st.session_state.api_key or None
                                )
                                st.session_state.case_state = reloaded
                                st.session_state.executor = executor
                                st.session_state.pending_auto_result = None
                                st.session_state.editing_step_id = None
                                st.rerun()
                    with btn_cols[2]:
                        if st.button(
                            "Delete", key=f"del_{real_idx}", use_container_width=True
                        ):
                            st.session_state.cases_history.pop(real_idx)
                            _save_cases_history(st.session_state.cases_history)
                            st.rerun()
        return

    # Back button — always visible, left-aligned
    if st.button("\u2190 Back to Cases", key="back_to_cases"):
        # Save incomplete case so user can resume later
        if state.status != "completed":
            # Remove any existing entry for this case
            st.session_state.cases_history = [
                c
                for c in st.session_state.cases_history
                if c.get("case_id") != state.case_id
            ]
            st.session_state.cases_history.append(
                {
                    "case_id": state.case_id,
                    "client_name": state.client_data.get("name", "Unknown"),
                    "risk_level": state.client_data.get("risk_level", "standard"),
                    "steps_completed": len(state.completed_steps),
                    "decisions": len(state.decisions_made),
                    "status": "incomplete",
                    "timestamp": datetime.now().isoformat(),
                    "client_data": state.client_data,
                    "completed_steps": state.completed_steps,
                    "step_results": state.step_results,
                    "decisions_made": state.decisions_made,
                    "current_step_id": state.current_step_id,
                }
            )
            _save_cases_history(st.session_state.cases_history)
        st.session_state.case_state = None
        st.session_state.executor = None
        st.session_state.pending_auto_result = None
        st.session_state.editing_step_id = None
        st.rerun()

    # Progress
    progress = executor.get_progress(state)
    prog_col1, prog_col2, prog_col3 = st.columns(3)
    prog_col1.metric("Coverage", f"{progress['percentage']}%")
    prog_col2.metric("Steps Visited", f"{progress['completed']}/{progress['total']}")
    prog_col3.metric("Status", state.status.replace("_", " ").title())

    st.progress(progress["percentage"] / 100)

    # Layout: graph + current step
    col_graph, col_step = st.columns([2, 3])

    with col_graph:
        dot = render_workflow_graph(wf, state.current_step_id, state.completed_steps)
        st.graphviz_chart(dot, width="stretch")

    with col_step:
        if state.status == "completed":
            # Store in history for analytics (do this first so it's saved)
            if not any(
                c["case_id"] == state.case_id for c in st.session_state.cases_history
            ):
                st.session_state.cases_history.append(
                    {
                        "case_id": state.case_id,
                        "client_name": state.client_data.get("name", "Unknown"),
                        "risk_level": state.client_data.get("risk_level", "standard"),
                        "steps_completed": len(state.completed_steps),
                        "decisions": len(state.decisions_made),
                        "status": state.status,
                        "timestamp": datetime.now().isoformat(),
                        # Full state for reload / audit
                        "client_data": state.client_data,
                        "completed_steps": state.completed_steps,
                        "step_results": state.step_results,
                        "decisions_made": state.decisions_made,
                        "current_step_id": state.current_step_id,
                    }
                )
                _save_cases_history(st.session_state.cases_history)

            st.success("**Case Complete — saved to history.**")

            # Show all gathered data with edit/restart options
            _render_previous_results(state, wf)

            _render_audit_trail(state, wf)

            # ── Export & Actions ──
            act1, act2 = st.columns(2)
            with act1:
                audit_csv = _generate_audit_csv(state, wf)
                st.download_button(
                    "Export Audit Report (CSV)",
                    data=audit_csv,
                    file_name=f"audit_report_{state.case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width="stretch",
                )
            with act2:
                if st.button(
                    "Start New Case", type="primary", use_container_width=True
                ):
                    st.session_state.case_state = None
                    st.session_state.executor = None
                    st.session_state.pending_auto_result = None
                    st.session_state.editing_step_id = None
                    st.rerun()
            return

        if state.status == "blocked":
            st.error("Case blocked — no valid path forward")
            return

        current_step = executor.get_current_step(state)
        if not current_step:
            st.error("No current step found")
            return

        # Show ALL previous step results so the reviewer has full context
        _render_previous_results(state, wf)

        # Current step display
        st.subheader(f"Current: {current_step.title}")
        st.write(
            f"**Type:** {current_step.step_type.value} | **Owner:** {current_step.owner}"
        )
        st.write(current_step.description)

        st.divider()

        # Handle step based on type
        if current_step.step_type == StepType.START:
            if st.button("Begin Process", type="primary"):
                state = executor.advance(state)
                st.session_state.case_state = state
                st.rerun()

        elif current_step.step_type == StepType.AUTO:
            pending = st.session_state.pending_auto_result

            if pending and pending.get("step_id") == current_step.id:
                # ── Phase 2: Review / Edit / Override the result ──
                result = pending["result"]
                st.success("Auto step executed — review the result below.")
                _render_step_result_card(current_step.title, result)

                # Editable override section
                with st.expander("Edit or Override Result", expanded=False):
                    with st.form(f"override_{current_step.id}"):
                        edited_result_text = st.text_area(
                            "Result summary:",
                            value=result.get("result", ""),
                            height=80,
                        )
                        # Editable data fields
                        data = result.get("data_gathered", {})
                        edited_data = {}
                        if data:
                            st.markdown("**Data Fields:**")
                            for k, v in data.items():
                                label = k.replace("_", " ").title()
                                if isinstance(v, bool):
                                    edited_data[k] = st.checkbox(label, value=v)
                                else:
                                    edited_data[k] = st.text_input(
                                        label,
                                        value=(
                                            str(v)
                                            if not isinstance(v, list)
                                            else ", ".join(str(i) for i in v)
                                        ),
                                    )

                        edited_flags = st.text_input(
                            "Flags (comma-separated):",
                            value=", ".join(result.get("flags", [])),
                        )
                        edited_status = st.selectbox(
                            "Status:",
                            ["completed", "needs_review", "failed"],
                            index=(
                                ["completed", "needs_review", "failed"].index(
                                    result.get("status", "completed")
                                )
                                if result.get("status", "completed")
                                in ["completed", "needs_review", "failed"]
                                else 0
                            ),
                        )
                        override_submitted = st.form_submit_button(
                            "Save Edits", type="primary"
                        )
                        if override_submitted:
                            # Build overridden result
                            overridden = dict(result)
                            overridden["result"] = edited_result_text
                            overridden["status"] = edited_status
                            overridden["flags"] = [
                                f.strip() for f in edited_flags.split(",") if f.strip()
                            ]
                            if edited_data:
                                overridden["data_gathered"] = edited_data
                            overridden["overridden"] = True
                            st.session_state.pending_auto_result = {
                                "step_id": current_step.id,
                                "result": overridden,
                            }
                            st.rerun()

                # Accept / Continue button
                col_accept, col_reject = st.columns(2)
                with col_accept:
                    if st.button(
                        "Accept & Continue", type="primary", key="accept_auto"
                    ):
                        final_result = st.session_state.pending_auto_result["result"]
                        st.session_state.pending_auto_result = None
                        state = executor.advance(state, auto_result=final_result)
                        st.session_state.case_state = state
                        st.rerun()
                with col_reject:
                    if st.button("Re-run Step", key="rerun_auto"):
                        st.session_state.pending_auto_result = None
                        st.rerun()

            else:
                # ── Phase 1: Execute the auto step ──
                st.info("This step will be executed automatically by the system")
                if st.button("Execute Auto Step", type="primary"):
                    placeholder = st.empty()
                    with placeholder.container():
                        with st.spinner(f"Executing: {current_step.title}..."):
                            result = executor.execute_auto_step(state, current_step)
                            time.sleep(1.5)

                    placeholder.empty()

                    # Store pending result for review
                    st.session_state.pending_auto_result = {
                        "step_id": current_step.id,
                        "result": result,
                    }
                    st.rerun()

        elif current_step.step_type == StepType.HUMAN:
            # ── Contextual form fields per step ──
            _human_forms = {
                "enhanced_due_diligence": {
                    "title": "Enhanced Due Diligence Review",
                    "guidance": "Review screening results, obtain additional information, and document your assessment below.",
                    "fields": [
                        {
                            "key": "source_of_funds",
                            "label": "Source of Funds / Wealth",
                            "type": "area",
                            "placeholder": "Describe the client's reported source of funds and supporting evidence…",
                        },
                        {
                            "key": "business_purpose",
                            "label": "Business Relationship Purpose",
                            "type": "area",
                            "placeholder": "Why is the client opening this account? What is the intended use?",
                        },
                        {
                            "key": "adverse_media",
                            "label": "Adverse Media / Public Database Findings",
                            "type": "area",
                            "placeholder": "Summarise results from public database & media searches…",
                        },
                        {
                            "key": "rationale",
                            "label": "Risk Acceptance Rationale",
                            "type": "area",
                            "placeholder": "Explain why this client should / should not be onboarded despite elevated risk…",
                        },
                        {
                            "key": "senior_approval",
                            "label": "Senior Compliance Officer Approval",
                            "type": "select",
                            "options": [
                                "Pending",
                                "Approved by SCO",
                                "Declined by SCO",
                            ],
                        },
                    ],
                    "decision_options": [
                        "Approved — Proceed",
                        "Needs Follow-up",
                        "Rejected — Decline Application",
                    ],
                },
                "verify_photo_id": {
                    "title": "Government Photo ID Verification",
                    "guidance": "Review the uploaded photo ID and liveness check results. Confirm identity match.",
                    "fields": [
                        {
                            "key": "doc_type",
                            "label": "Document Type",
                            "type": "select",
                            "options": [
                                "Passport",
                                "Driver's Licence",
                                "PR Card",
                                "Other Gov. Photo ID",
                            ],
                        },
                        {
                            "key": "doc_number",
                            "label": "Document Number",
                            "type": "text",
                            "placeholder": "e.g., AB123456",
                        },
                        {
                            "key": "doc_jurisdiction",
                            "label": "Issuing Jurisdiction",
                            "type": "text",
                            "placeholder": "e.g., Ontario, Canada",
                        },
                        {
                            "key": "doc_expiry",
                            "label": "Expiry Date",
                            "type": "text",
                            "placeholder": "YYYY-MM-DD",
                        },
                        {
                            "key": "name_match",
                            "label": "Name matches application?",
                            "type": "select",
                            "options": [
                                "Yes — exact match",
                                "Yes — minor variation",
                                "No — mismatch",
                            ],
                        },
                        {
                            "key": "liveness_check",
                            "label": "Liveness Detection Result",
                            "type": "select",
                            "options": ["Passed", "Inconclusive", "Failed"],
                        },
                        {
                            "key": "tampering",
                            "label": "Signs of Tampering?",
                            "type": "select",
                            "options": [
                                "None detected",
                                "Suspicious — needs review",
                                "Tampering confirmed",
                            ],
                        },
                        {
                            "key": "observations",
                            "label": "Verification Notes",
                            "type": "area",
                            "placeholder": "Any additional observations about document authenticity…",
                        },
                    ],
                    "decision_options": [
                        "Verified — Identity Confirmed",
                        "Needs Follow-up",
                        "Rejected — Verification Failed",
                    ],
                },
                "dual_process_verify": {
                    "title": "Dual-Process Verification",
                    "guidance": "Two documents from different categories are required. Verify name match on both and confirm one additional identifier.",
                    "fields": [
                        {
                            "key": "doc_a_type",
                            "label": "Document A — Type & Category",
                            "type": "select",
                            "options": [
                                "Birth Certificate (Gov.)",
                                "CRA Notice of Assessment (Gov.)",
                                "SIN Confirmation (Gov.)",
                                "Other Gov. Document",
                            ],
                        },
                        {
                            "key": "doc_a_detail",
                            "label": "Document A — Details",
                            "type": "text",
                            "placeholder": "Document number, issuing body, date…",
                        },
                        {
                            "key": "doc_b_type",
                            "label": "Document B — Type & Category",
                            "type": "select",
                            "options": [
                                "Bank Statement (Financial)",
                                "Credit Card Statement (Financial)",
                                "Utility Bill (Institutional)",
                                "Insurance Policy (Institutional)",
                            ],
                        },
                        {
                            "key": "doc_b_detail",
                            "label": "Document B — Details",
                            "type": "text",
                            "placeholder": "Account number (last 4), statement date, provider…",
                        },
                        {
                            "key": "name_match_both",
                            "label": "Name matches on BOTH documents?",
                            "type": "select",
                            "options": [
                                "Yes — exact match",
                                "Yes — minor variation",
                                "No — mismatch",
                            ],
                        },
                        {
                            "key": "additional_id",
                            "label": "Additional Identifier Confirmed",
                            "type": "select",
                            "options": [
                                "DOB match",
                                "Address match",
                                "Other identifier",
                            ],
                        },
                        {
                            "key": "notes",
                            "label": "Verification Notes",
                            "type": "area",
                            "placeholder": "Any discrepancies or observations…",
                        },
                    ],
                    "decision_options": [
                        "Verified — Identity Confirmed",
                        "Needs Follow-up",
                        "Rejected — Verification Failed",
                    ],
                },
                "escalate_senior": {
                    "title": "Senior Compliance Escalation",
                    "guidance": "Review the failed verification attempt. Determine next steps and document your decision.",
                    "fields": [
                        {
                            "key": "failure_reason",
                            "label": "Reason for Verification Failure",
                            "type": "area",
                            "placeholder": "Describe why the previous verification method failed…",
                        },
                        {
                            "key": "attempts_summary",
                            "label": "Verification Attempts Summary",
                            "type": "area",
                            "placeholder": "List all verification methods attempted and their outcomes…",
                        },
                        {
                            "key": "recommended_action",
                            "label": "Recommended Action",
                            "type": "select",
                            "options": [
                                "Try alternative verification method",
                                "Request additional documents from client",
                                "Decline application",
                                "File STR with FINTRAC",
                            ],
                        },
                        {
                            "key": "str_consideration",
                            "label": "STR Filing Considered?",
                            "type": "select",
                            "options": [
                                "No — no suspicious indicators",
                                "Yes — indicators present, filing recommended",
                                "Yes — STR filed",
                            ],
                        },
                        {
                            "key": "rationale",
                            "label": "Decision Rationale",
                            "type": "area",
                            "placeholder": "Document reasoning for the chosen course of action (required for audit trail)…",
                        },
                    ],
                    "decision_options": [
                        "Resolved — Proceed with Alt. Method",
                        "Application Declined",
                        "STR Filed — Application Declined",
                    ],
                },
            }

            form_cfg = _human_forms.get(current_step.id)
            if not form_cfg:
                # Try without visio_ prefix
                form_cfg = _human_forms.get(current_step.id.replace("visio_", ""))

            if form_cfg:
                # ── Step-specific contextual form ──
                st.info(f"🔍 **{form_cfg['title']}** — {form_cfg['guidance']}")
                with st.form(f"human_step_{current_step.id}"):
                    field_values = {}
                    for fld in form_cfg["fields"]:
                        if fld["type"] == "area":
                            field_values[fld["key"]] = st.text_area(
                                fld["label"],
                                placeholder=fld.get("placeholder", ""),
                                key=f"hf_{current_step.id}_{fld['key']}",
                            )
                        elif fld["type"] == "text":
                            field_values[fld["key"]] = st.text_input(
                                fld["label"],
                                placeholder=fld.get("placeholder", ""),
                                key=f"hf_{current_step.id}_{fld['key']}",
                            )
                        elif fld["type"] == "select":
                            field_values[fld["key"]] = st.selectbox(
                                fld["label"],
                                fld.get("options", []),
                                key=f"hf_{current_step.id}_{fld['key']}",
                            )
                    st.divider()
                    decision_opts = form_cfg.get(
                        "decision_options", ["Approved", "Needs Follow-up", "Rejected"]
                    )
                    approved = st.radio(
                        "Decision:", decision_opts, key=f"hd_{current_step.id}"
                    )
                    submitted = st.form_submit_button("Complete Step", type="primary")
                    if submitted:
                        result = {
                            **field_values,
                            "decision": approved,
                            "status": "completed",
                        }
                        state = executor.advance(state, human_input=result)
                        st.session_state.case_state = state
                        st.rerun()
            else:
                # ── Generic fallback form — use step description as context ──
                st.info(
                    f"📋 **{current_step.title}** — This step requires your review and input."
                )
                with st.form(f"human_step_{current_step.id}"):
                    action_taken = st.text_area(
                        f"Describe action taken for: *{current_step.title}*",
                        placeholder=f"Based on step instructions: {current_step.description[:120]}…",
                    )
                    notes = st.text_input(
                        "Additional notes:", placeholder="Any flags or observations"
                    )
                    approved = st.radio(
                        "Decision:", ["Approved", "Needs Follow-up", "Rejected"]
                    )
                    submitted = st.form_submit_button("Complete Step", type="primary")
                    if submitted:
                        result = {
                            "action": action_taken,
                            "notes": notes,
                            "decision": approved,
                            "status": "completed",
                        }
                        state = executor.advance(state, human_input=result)
                        st.session_state.case_state = state
                        st.rerun()

        elif current_step.step_type == StepType.DECISION:
            st.info("Choose the appropriate path:")
            branch_labels = list(current_step.branches.keys())
            branch_display = []
            for label in branch_labels:
                target_id = current_step.branches[label]
                target_step = wf.steps.get(target_id)
                target_name = target_step.title if target_step else target_id
                branch_display.append(f"{label} → {target_name}")
            chosen_idx = st.radio(
                "Decision:",
                range(len(branch_labels)),
                format_func=lambda i: branch_display[i],
                key=f"decision_radio_{current_step.id}",
                label_visibility="collapsed",
            )
            if st.button(
                "Confirm Decision",
                type="primary",
                key=f"confirm_decision_{current_step.id}",
            ):
                chosen_label = branch_labels[chosen_idx]
                state = executor.advance(state, decision=chosen_label)
                st.session_state.case_state = state
                st.rerun()

        elif current_step.step_type == StepType.END:
            if st.button("Complete Process", type="primary"):
                state = executor.advance(state)
                st.session_state.case_state = state
                st.rerun()

    # Audit trail
    if state.completed_steps:
        with st.expander("Audit Trail", expanded=False):
            _render_audit_trail(state, wf)


def _render_previous_results(state: CaseState, wf: Workflow):
    """Show all completed step results with edit & restart-from options."""
    # Collect steps that have meaningful results (skip empty / START)
    result_steps = []
    for sid in state.completed_steps:
        step = wf.steps.get(sid)
        if not step:
            continue
        res = state.step_results.get(sid, {})
        if step.step_type == StepType.START:
            continue
        if not res:
            continue
        result_steps.append((sid, step, res))

    if not result_steps:
        return

    with st.expander(
        f"Data Gathered So Far  ({len(result_steps)} step{'s' if len(result_steps) != 1 else ''})",
        expanded=True,
    ):
        for i, (sid, step, res) in enumerate(result_steps):
            is_latest = i == len(result_steps) - 1
            status = res.get("status", "completed")
            icon = (
                "\u2705"
                if status == "completed"
                else "\u26a0\ufe0f" if status == "needs_review" else "\u274c"
            )
            with st.expander(f"{icon} {step.title}", expanded=is_latest):

                # Check if we are editing this step
                if st.session_state.editing_step_id == sid:
                    _render_edit_step_form(sid, step, res, state)
                else:
                    _render_step_result_card(step.title, res)
                    # Action buttons row
                    col_edit, col_restart = st.columns(2)
                    with col_edit:
                        if st.button("Edit Result", key=f"edit_{sid}"):
                            st.session_state.editing_step_id = sid
                            st.rerun()
                    with col_restart:
                        if st.button("Restart From Here", key=f"restart_{sid}"):
                            _restart_from_step(state, sid)
                            st.rerun()


def _render_edit_step_form(step_id: str, step: Step, result: dict, state: CaseState):
    """Render an inline form to edit a completed step's result."""
    with st.form(f"edit_form_{step_id}"):
        st.markdown(f"**Editing: {step.title}**")

        edited_result_text = st.text_area(
            "Result summary:",
            value=result.get("result", result.get("action", "")),
            height=80,
        )

        # Editable data fields
        data = result.get("data_gathered", {})
        edited_data = {}
        if data:
            st.markdown("**Data Fields:**")
            for k, v in data.items():
                label = k.replace("_", " ").title()
                if isinstance(v, bool):
                    edited_data[k] = st.checkbox(
                        label, value=v, key=f"ed_{step_id}_{k}"
                    )
                else:
                    edited_data[k] = st.text_input(
                        label,
                        value=(
                            str(v)
                            if not isinstance(v, list)
                            else ", ".join(str(x) for x in v)
                        ),
                        key=f"ed_{step_id}_{k}",
                    )

        edited_notes = st.text_input(
            "Notes:",
            value=result.get("notes", ""),
            key=f"ed_{step_id}_notes",
        )
        edited_flags = st.text_input(
            "Flags (comma-separated):",
            value=", ".join(result.get("flags", [])),
            key=f"ed_{step_id}_flags",
        )
        edited_status = st.selectbox(
            "Status:",
            ["completed", "needs_review", "failed"],
            index=(
                ["completed", "needs_review", "failed"].index(
                    result.get("status", "completed")
                )
                if result.get("status", "completed")
                in ["completed", "needs_review", "failed"]
                else 0
            ),
            key=f"ed_{step_id}_status",
        )

        col_save, col_cancel = st.columns(2)
        with col_save:
            save = st.form_submit_button("Save Changes", type="primary")
        with col_cancel:
            cancel = st.form_submit_button("Cancel")

        if save:
            updated = dict(result)
            if "result" in result:
                updated["result"] = edited_result_text
            elif "action" in result:
                updated["action"] = edited_result_text
            updated["status"] = edited_status
            updated["notes"] = edited_notes
            updated["flags"] = [f.strip() for f in edited_flags.split(",") if f.strip()]
            if edited_data:
                updated["data_gathered"] = edited_data
            updated["edited"] = True
            state.step_results[step_id] = updated
            st.session_state.case_state = state
            st.session_state.editing_step_id = None
            st.rerun()

        if cancel:
            st.session_state.editing_step_id = None
            st.rerun()


def _restart_from_step(state: CaseState, target_step_id: str):
    """Rewind the workflow state to restart from a given step."""
    # Find the index of the target step in completed_steps
    if target_step_id not in state.completed_steps:
        return

    idx = state.completed_steps.index(target_step_id)

    # Remove this step and everything after it from completed
    steps_to_remove = state.completed_steps[idx:]
    state.completed_steps = state.completed_steps[:idx]

    # Clean up results and decisions for removed steps
    for sid in steps_to_remove:
        state.step_results.pop(sid, None)
        state.decisions_made.pop(sid, None)

    # Set current step to the target
    state.current_step_id = target_step_id
    state.status = "in_progress"

    # Clear any pending auto result
    st.session_state.pending_auto_result = None
    st.session_state.editing_step_id = None
    st.session_state.case_state = state


def _render_step_result_card(step_title: str, result: dict):
    """Render a nicely formatted result card for a completed step."""
    flags = result.get("flags", [])
    status = result.get("status", "completed")
    result_text = result.get("result", "Completed")
    data = result.get("data_gathered", {})

    # Status badge
    if status in ("needs_review", "failed"):
        st.error(f"**{step_title}** - {status.upper()}")
        border_color = "#f44336"
        bg_color = "#FFEBEE"
    elif flags:
        st.warning(f"**{step_title}** - COMPLETED WITH FLAGS")
        border_color = "#FF9800"
        bg_color = "#FFF8E1"
    else:
        st.success(f"**{step_title}** - COMPLETED")
        border_color = "#4CAF50"
        bg_color = "#E8F5E9"

    # Confidence badge
    confidence = result.get("confidence_score")
    if confidence is not None:
        pct = (
            int(confidence * 100)
            if isinstance(confidence, float) and confidence <= 1
            else int(confidence)
        )
        if pct >= 90:
            conf_color, conf_bg = "#1B5E20", "#C8E6C9"
        elif pct >= 70:
            conf_color, conf_bg = "#E65100", "#FFE0B2"
        else:
            conf_color, conf_bg = "#B71C1C", "#FFCDD2"
        conf_badge = (
            f"<span style='display:inline-block; margin-left:8px; padding:2px 10px; "
            f"border-radius:12px; background:{conf_bg}; color:{conf_color}; "
            f"font-weight:600; font-size:0.82rem;'>"
            f"Confidence: {pct}%</span>"
        )
    else:
        conf_badge = ""

    # Build human-readable output
    lines = [f"<strong>{result_text}</strong>{conf_badge}"]

    if data:
        lines.append(
            "<br><br><strong>Details:</strong><ul style='margin:4px 0 0 0; padding-left:20px;'>"
        )
        for k, v in data.items():
            label = k.replace("_", " ").title()
            if isinstance(v, bool):
                v = "Yes" if v else "No"
            elif isinstance(v, list):
                v = ", ".join(str(i) for i in v) if v else "None"
            lines.append(f"<li><strong>{label}:</strong> {v}</li>")
        lines.append("</ul>")

    if flags:
        lines.append(
            "<br><strong>Flags:</strong><ul style='margin:4px 0 0 0; padding-left:20px;'>"
        )
        for flag in flags:
            lines.append(f"<li>{flag}</li>")
        lines.append("</ul>")

    html = (
        f"<div style='background:{bg_color}; padding:14px 16px; border-radius:8px; "
        f"border-left:4px solid {border_color}; margin:8px 0; font-size:0.95rem;'>"
        + "".join(lines)
        + "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    st.write("")


def _render_audit_trail(state: CaseState, wf: Workflow):
    """Render the completed steps as a human-readable audit trail."""
    for i, step_id in enumerate(state.completed_steps):
        step = wf.steps.get(step_id)
        result = state.step_results.get(step_id, {})
        if step:
            type_icon = {
                "START": "▶",
                "END": "■",
                "AUTO": "⚙",
                "HUMAN": "👤",
                "DECISION": "◇",
            }.get(step.step_type.value, "•")
            st.markdown(f"**{type_icon} {i+1}. {step.title}**")

            if step_id in state.decisions_made:
                st.markdown(f"↳ Decision: **{state.decisions_made[step_id]}**")

            if result:
                # Human-friendly formatting instead of raw JSON
                result_text = result.get("result", result.get("action", ""))
                status = result.get("status", result.get("decision", "completed"))
                data = result.get("data_gathered", {})
                notes = result.get("notes", "")
                flags = result.get("flags", [])

                parts = []
                if result_text:
                    parts.append(f"**Result:** {result_text}")
                if status and status != "completed":
                    parts.append(f"**Status:** {status}")
                if notes:
                    parts.append(f"**Notes:** {notes}")
                if data:
                    data_parts = []
                    for k, v in data.items():
                        label = k.replace("_", " ").title()
                        if isinstance(v, bool):
                            v = "Yes" if v else "No"
                        elif isinstance(v, list):
                            v = ", ".join(str(x) for x in v) if v else "None"
                        data_parts.append(f"{label}: {v}")
                    parts.append("**Data:** " + " | ".join(data_parts))
                if flags:
                    parts.append("**Flags:** " + ", ".join(flags))

                for p in parts:
                    st.caption(p)
            st.divider()


def _generate_audit_csv(state: CaseState, wf: Workflow) -> str:
    """Generate a CSV audit report for a completed case."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Step #",
            "Step ID",
            "Step Title",
            "Step Type",
            "Owner",
            "Decision Made",
            "Action Taken",
            "Result Status",
            "Notes",
        ]
    )
    for i, step_id in enumerate(state.completed_steps):
        step = wf.steps.get(step_id)
        result = state.step_results.get(step_id, {})
        decision = state.decisions_made.get(step_id, "")
        writer.writerow(
            [
                i + 1,
                step_id,
                step.title if step else "Unknown",
                step.step_type.value if step else "N/A",
                step.owner if step else "N/A",
                decision,
                result.get("action", result.get("result", "")),
                result.get("decision", result.get("status", "completed")),
                result.get("notes", ""),
            ]
        )
    # Header info
    header = io.StringIO()
    header.write(f"AUDIT REPORT — Case {state.case_id}\n")
    header.write(f"Client: {state.client_data.get('name', 'N/A')}\n")
    header.write(f"Risk Level: {state.client_data.get('risk_level', 'N/A')}\n")
    header.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    header.write(f"Status: {state.status.replace('_', ' ').title()}\n\n")
    return header.getvalue() + output.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Tab: TRAIN
# ─────────────────────────────────────────────────────────────────────────────


def render_train_tab():
    """Training mode — practice with generated scenarios."""
    wf = st.session_state.workflow
    if not wf:
        st.markdown(
            '<div class="empty-state">'
            "<h3>Training Mode</h3>"
            "<p>Parse or load a document first, then practice with AI-generated scenarios.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.subheader("Training Mode")
    st.caption(
        "Practice executing the workflow with AI-generated scenarios. Test your knowledge on each step."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Generate New Scenario", type="primary", width="stretch"):
            with st.spinner("Generating training scenario..."):
                scenario = generate_training_scenario(
                    wf, st.session_state.api_key or None
                )
            st.session_state.training_scenario = scenario
            st.session_state.training_score = 0
            st.session_state.training_total = 0
            st.session_state.training_step_index = 0
            st.rerun()

    with col2:
        if st.session_state.training_total > 0:
            score_pct = round(
                st.session_state.training_score / st.session_state.training_total * 100
            )
            st.metric(
                "Score",
                f"{st.session_state.training_score}/{st.session_state.training_total} ({score_pct}%)",
            )

    scenario = st.session_state.training_scenario
    if not scenario:
        st.markdown(
            '<div class="empty-state" style="padding:32px;">'
            "<h3>Generate a Scenario</h3>"
            "<p>Click <strong>Generate New Scenario</strong> to start a training quiz.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        # ── Show training history ──
        t_history = st.session_state.training_history
        if t_history:
            st.divider()
            st.markdown("#### Training History")
            for t_idx, attempt in enumerate(reversed(t_history)):
                t_real_idx = len(t_history) - 1 - t_idx
                ts = attempt.get("timestamp", "")[:16].replace("T", " at ")
                pct = attempt.get("percentage", 0)
                t_status = attempt.get("status", "completed")
                if t_status == "incomplete":
                    passed = "INCOMPLETE"
                else:
                    passed = "PASS" if pct >= 80 else "REVIEW" if pct >= 60 else "FAIL"
                label = f"{attempt.get('score', 0)}/{attempt.get('total', 0)} ({pct}%) — {passed}  |  {ts}"

                with st.expander(label, expanded=False):
                    if attempt.get("scenario_title"):
                        st.markdown(f"**Scenario:** {attempt['scenario_title']}")
                    answers = attempt.get("answers", [])
                    if answers:
                        for a in answers:
                            q_num = a.get("question_num", "?")
                            is_correct = a.get("is_correct", False)
                            status_txt = "Correct" if is_correct else "Incorrect"
                            st.markdown(
                                f"**Q{q_num}: {a.get('step_title', '')}** — {status_txt}"
                            )
                            st.markdown(
                                f"&nbsp;&nbsp;&nbsp;&nbsp;{a.get('question', '')}"
                            )
                            if is_correct:
                                st.markdown(
                                    f"&nbsp;&nbsp;&nbsp;&nbsp;Your answer: **{a.get('user_answer', '')}**"
                                )
                            else:
                                st.markdown(
                                    f"&nbsp;&nbsp;&nbsp;&nbsp;Your answer: ~~{a.get('user_answer', '')}~~"
                                )
                                st.markdown(
                                    f"&nbsp;&nbsp;&nbsp;&nbsp;Correct answer: **{a.get('correct_answer', '')}**"
                                )
                            st.divider()
                    # Action buttons
                    tcols = st.columns(3)
                    with tcols[0]:
                        train_csv_data = _generate_training_csv_from(answers, attempt)
                        st.download_button(
                            "Export CSV",
                            data=train_csv_data,
                            file_name=f"training_{attempt.get('timestamp', '')[:10]}.csv",
                            mime="text/csv",
                            key=f"t_dl_{t_real_idx}",
                            use_container_width=True,
                        )
                    with tcols[1]:
                        if attempt.get("status") == "incomplete" and attempt.get(
                            "scenario"
                        ):
                            if st.button(
                                "Resume",
                                key=f"t_resume_{t_real_idx}",
                                use_container_width=True,
                            ):
                                st.session_state.training_scenario = attempt["scenario"]
                                st.session_state.training_step_index = attempt.get(
                                    "step_index", 0
                                )
                                st.session_state.training_score = attempt.get(
                                    "score", 0
                                )
                                st.session_state.training_total = attempt.get(
                                    "total", 0
                                )
                                st.session_state.training_answers = list(
                                    attempt.get("answers", [])
                                )
                                # Remove this incomplete entry
                                st.session_state.training_history.pop(t_real_idx)
                                _save_training_history(
                                    st.session_state.training_history
                                )
                                st.rerun()
                    with tcols[2]:
                        if st.button(
                            "Delete",
                            key=f"t_del_{t_real_idx}",
                            use_container_width=True,
                        ):
                            st.session_state.training_history.pop(t_real_idx)
                            _save_training_history(st.session_state.training_history)
                            st.rerun()
        return

    st.divider()

    # Back button — always visible, left-aligned above scenario
    if st.button("\u2190 Back to Training", key="back_to_training"):
        # Save incomplete training so user can resume
        scenario_title = scenario.get("scenario_title", "Training Scenario")
        total = st.session_state.training_total
        score = st.session_state.training_score
        pct = round(score / total * 100) if total else 0
        step_idx = st.session_state.training_step_index
        # Remove prior entry for this scenario if incomplete
        st.session_state.training_history = [
            h
            for h in st.session_state.training_history
            if not (
                h.get("scenario_title") == scenario_title
                and h.get("status") == "incomplete"
            )
        ]
        st.session_state.training_history.append(
            {
                "scenario_title": scenario_title,
                "score": score,
                "total": total,
                "percentage": pct,
                "answers": list(st.session_state.training_answers),
                "timestamp": datetime.now().isoformat(),
                "status": "incomplete",
                "step_index": step_idx,
                "scenario": scenario,
            }
        )
        _save_training_history(st.session_state.training_history)
        st.session_state.training_scenario = None
        st.session_state.training_step_index = 0
        st.rerun()

    # Scenario info
    st.subheader(f"{scenario.get('scenario_title', 'Training Scenario')}")
    st.write(scenario.get("scenario_description", ""))

    # Client card
    client = scenario.get("client", {})
    if client:
        with st.expander("Client Details", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.write(f"**Name:** {client.get('name', 'N/A')}")
                st.write(f"**DOB:** {client.get('date_of_birth', 'N/A')}")
                st.write(f"**Citizenship:** {client.get('citizenship', 'N/A')}")
                st.write(f"**Occupation:** {client.get('occupation', 'N/A')}")
            with c2:
                st.write(f"**Account Type:** {client.get('account_type', 'N/A')}")
                st.write(f"**Source of Funds:** {client.get('source_of_funds', 'N/A')}")
                st.write(f"**ID Document:** {client.get('id_document_type', 'N/A')}")
                st.write(f"**ID Expiry:** {client.get('id_expiry', 'N/A')}")
            if client.get("special_circumstances"):
                st.warning(
                    f"**Special Circumstances:** {client['special_circumstances']}"
                )

    st.divider()

    # Quiz through steps
    quiz_steps = [
        s
        for s in wf.steps.values()
        if s.step_type in (StepType.HUMAN, StepType.DECISION, StepType.AUTO)
    ]
    step_idx = st.session_state.training_step_index

    if step_idx < len(quiz_steps):
        current_quiz_step = quiz_steps[step_idx]
        st.subheader(
            f"Question {step_idx + 1} of {len(quiz_steps)}: {current_quiz_step.title}"
        )

        quiz = generate_step_quiz(
            current_quiz_step, scenario, st.session_state.api_key or None
        )

        st.write(f"**{quiz.get('question', 'What should happen at this step?')}**")

        options = quiz.get("options", ["Option A", "Option B", "Option C", "Option D"])
        correct_idx = quiz.get("correct_index", 0)

        # Check if we're showing feedback from the last answer
        feedback_key = f"feedback_{step_idx}"
        if feedback_key in st.session_state:
            fb = st.session_state[feedback_key]
            if fb["is_correct"]:
                st.markdown(
                    f"<div style='background:#E8F5E9; padding:16px; border-radius:10px; border-left:5px solid #4CAF50; margin:12px 0;'>"
                    f"<h3 style='color:#2E7D32; margin:0;'>✅ Correct!</h3>"
                    f"<p style='margin:8px 0 0 0;'>Your answer: <strong>{fb['user_answer']}</strong></p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div style='background:#FFEBEE; padding:16px; border-radius:10px; border-left:5px solid #f44336; margin:12px 0;'>"
                    f"<h3 style='color:#C62828; margin:0;'>❌ Incorrect</h3>"
                    f"<p style='margin:8px 0 0 0;'>Your answer: <strong>{fb['user_answer']}</strong></p>"
                    f"<p style='margin:4px 0 0 0;'>Correct answer: <strong>{fb['correct_answer']}</strong></p>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            st.info(f"**Explanation:** {fb['explanation']}")
            if st.button("Next Question →", type="primary", key=f"next_{step_idx}"):
                del st.session_state[feedback_key]
                st.session_state.training_step_index += 1
                st.rerun()
            return

        with st.form(f"quiz_{step_idx}"):
            answer = st.radio("Your answer:", options, key=f"answer_{step_idx}")
            submitted = st.form_submit_button("Submit Answer")

            if submitted:
                selected_idx = options.index(answer)
                st.session_state.training_total += 1
                is_correct = selected_idx == correct_idx

                if is_correct:
                    st.session_state.training_score += 1

                # Track answer for export
                st.session_state.training_answers.append(
                    {
                        "question_num": step_idx + 1,
                        "step_title": current_quiz_step.title,
                        "question": quiz.get("question", ""),
                        "user_answer": answer,
                        "correct_answer": options[correct_idx],
                        "is_correct": is_correct,
                    }
                )

                # Store feedback (step index advances on "Next Question")
                st.session_state[feedback_key] = {
                    "is_correct": is_correct,
                    "user_answer": answer,
                    "correct_answer": options[correct_idx],
                    "explanation": quiz.get("explanation", "N/A"),
                }
                st.rerun()
    else:
        # Training complete — save to history
        total = st.session_state.training_total
        score = st.session_state.training_score
        pct = round(score / total * 100) if total else 0

        # Save to history (once per scenario)
        scenario_title = scenario.get("scenario_title", "Training Scenario")
        if not any(
            h.get("scenario_title") == scenario_title
            and h.get("score") == score
            and h.get("total") == total
            for h in st.session_state.training_history
        ):
            st.session_state.training_history.append(
                {
                    "scenario_title": scenario_title,
                    "score": score,
                    "total": total,
                    "percentage": pct,
                    "answers": list(st.session_state.training_answers),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            _save_training_history(st.session_state.training_history)

        st.success("**Training Complete!**")
        if total > 0:
            st.metric("Final Score", f"{score}/{total} ({pct}%)")
            if pct >= 80:
                st.success("You passed! Ready for live case handling.")
            elif pct >= 60:
                st.warning("Review needed on some compliance areas.")
            else:
                st.error(
                    "Please retake the training — compliance understanding needs improvement."
                )

        # ── Review your answers ──
        if st.session_state.training_answers:
            st.divider()
            st.subheader("Review Your Answers")
            for a in st.session_state.training_answers:
                is_correct = a.get("is_correct", False)
                icon = "\u2705" if is_correct else "\u274c"
                st.markdown(f"**{icon} Q{a['question_num']}: {a['step_title']}**")
                st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;{a.get('question', '')}")
                if is_correct:
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;Your answer: **{a['user_answer']}** \u2714"
                    )
                else:
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;Your answer: ~~{a['user_answer']}~~"
                    )
                    st.markdown(
                        f"&nbsp;&nbsp;&nbsp;&nbsp;Correct answer: **{a['correct_answer']}**"
                    )
                st.divider()

        # Learning points
        if scenario.get("key_learning_points"):
            st.subheader("Key Learning Points")
            for point in scenario["key_learning_points"]:
                st.write(f"• {point}")

        if scenario.get("trick_elements"):
            st.subheader("What to Watch For")
            for trick in scenario["trick_elements"]:
                st.write(f"• {trick}")

        # ── Export & Actions ──
        t_act1, t_act2 = st.columns(2)
        with t_act1:
            if st.session_state.training_answers:
                train_csv = _generate_training_csv()
                st.download_button(
                    "Export Training Record (CSV)",
                    data=train_csv,
                    file_name=f"training_record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
        with t_act2:
            if st.button(
                "Start New Scenario", type="primary", use_container_width=True
            ):
                st.session_state.training_scenario = None
                st.session_state.training_step_index = 0
                st.session_state.training_score = 0
                st.session_state.training_total = 0
                st.session_state.training_answers = []
                st.rerun()


def _generate_training_csv() -> str:
    """Generate a CSV training completion record."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Question #", "Step", "Question", "User Answer", "Correct Answer", "Result"]
    )
    for a in st.session_state.training_answers:
        writer.writerow(
            [
                a["question_num"],
                a["step_title"],
                a["question"],
                a["user_answer"],
                a["correct_answer"],
                "✓ Correct" if a["is_correct"] else "✗ Incorrect",
            ]
        )
    total = st.session_state.training_total
    score = st.session_state.training_score
    pct = round(score / total * 100) if total else 0
    header = io.StringIO()
    header.write(f"TRAINING COMPLETION RECORD\n")
    header.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    header.write(
        f"SOP: {st.session_state.workflow.name if st.session_state.workflow else 'N/A'}\n"
    )
    header.write(f"Score: {score}/{total} ({pct}%)\n")
    header.write(
        f"Result: {'PASS' if pct >= 80 else 'NEEDS REVIEW' if pct >= 60 else 'FAIL'}\n\n"
    )
    return header.getvalue() + output.getvalue()


def _generate_training_csv_from(answers: list, attempt: dict) -> str:
    """Generate a CSV training record from a saved history attempt."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Question #", "Step", "Question", "User Answer", "Correct Answer", "Result"]
    )
    for a in answers:
        writer.writerow(
            [
                a.get("question_num", ""),
                a.get("step_title", ""),
                a.get("question", ""),
                a.get("user_answer", ""),
                a.get("correct_answer", ""),
                "\u2713 Correct" if a.get("is_correct") else "\u2717 Incorrect",
            ]
        )
    score = attempt.get("score", 0)
    total = attempt.get("total", 0)
    pct = attempt.get("percentage", 0)
    header = io.StringIO()
    header.write("TRAINING COMPLETION RECORD\n")
    header.write(f"Date: {attempt.get('timestamp', 'N/A')}\n")
    header.write(f"Scenario: {attempt.get('scenario_title', 'N/A')}\n")
    header.write(f"Score: {score}/{total} ({pct}%)\n")
    header.write(
        f"Result: {'PASS' if pct >= 80 else 'NEEDS REVIEW' if pct >= 60 else 'FAIL'}\n\n"
    )
    return header.getvalue() + output.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# Tab: ANALYTICS
# ─────────────────────────────────────────────────────────────────────────────


def render_analytics_tab():
    """Show operational analytics and metrics."""
    st.subheader("Operational Analytics")

    # ── SOP Selector (from library + currently active) ──
    library = _load_library()
    active_wf = st.session_state.workflow
    selected_wf = None

    # Build option list from library entries
    sop_options: list[str] = []
    sop_workflows: list[dict | None] = []

    # If there's an active workflow not in the library, put it first
    active_in_library = False
    if active_wf and library:
        active_in_library = any(
            e["name"] == active_wf.name
            and e.get("source_format") == active_wf.source_format
            for e in library
        )

    if active_wf and not active_in_library:
        sop_options.append(
            f"{active_wf.name} ({active_wf.source_format.upper()}, {len(active_wf.steps)} steps)"
        )
        sop_workflows.append(None)  # sentinel: use active_wf

    for e in library:
        sop_options.append(
            f"{e['name']} ({e.get('source_format', '?').upper()}, {e.get('step_count', '?')} steps)"
        )
        sop_workflows.append(e)

    if sop_options:
        # Pre-select the currently active workflow
        default_idx = 0
        if active_wf and active_in_library:
            for i, e in enumerate(sop_workflows):
                if (
                    e
                    and e["name"] == active_wf.name
                    and e.get("source_format") == active_wf.source_format
                ):
                    default_idx = i
                    break

        selected_idx = st.selectbox(
            "Select document to analyze",
            range(len(sop_options)),
            index=default_idx,
            format_func=lambda i: sop_options[i],
            help="Pick any saved document from the library",
        )
        entry = sop_workflows[selected_idx]
        if entry is None:
            selected_wf = active_wf
        else:
            selected_wf = Workflow.from_dict(entry["workflow"])
    else:
        st.markdown(
            '<div class="empty-state" style="padding:32px;">'
            "<h3>No Documents Available</h3>"
            "<p>Parse or load a document from the sidebar to view analytics.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Workflow Composition ──
    if selected_wf:
        st.markdown("#### Workflow Composition")
        stats = selected_wf.get_stats()
        comp_cols = st.columns(5)
        type_labels = {
            "AUTO": "Auto",
            "HUMAN": "Human",
            "DECISION": "Decision",
            "START": "Start",
            "END": "End",
        }
        for i, (tc, count) in enumerate(stats["type_counts"].items()):
            comp_cols[i % 5].metric(type_labels.get(tc, tc), count)

        # Automation ratio
        auto_count = stats["type_counts"].get("AUTO", 0)
        human_count = stats["type_counts"].get("HUMAN", 0)
        total_actionable = auto_count + human_count
        if total_actionable > 0:
            auto_pct = round(auto_count / total_actionable * 100)
            st.metric(
                "Automation Rate",
                f"{auto_pct}%",
                help="Percentage of actionable steps handled by AI",
            )
            st.progress(auto_pct / 100)

        # Step type distribution chart
        import pandas as pd
        import altair as alt

        node_colors = {
            "Start": "#4CAF50",
            "End": "#f44336",
            "Auto": "#2196F3",
            "Human": "#9C27B0",
            "Decision": "#FF9800",
        }
        chart_labels = [type_labels.get(k, k) for k in stats["type_counts"].keys()]
        chart_data = pd.DataFrame(
            {
                "Step Type": chart_labels,
                "Count": list(stats["type_counts"].values()),
            }
        )
        color_scale = alt.Scale(
            domain=chart_labels,
            range=[node_colors.get(l, "#1A1A2E") for l in chart_labels],
        )
        top_chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X(
                    "Step Type:N",
                    sort=chart_labels,
                    axis=alt.Axis(labelAngle=0, title=None),
                    scale=alt.Scale(padding=0.4),
                ),
                y=alt.Y("Count:Q", axis=alt.Axis(tickMinStep=1, title="Count")),
                color=alt.Color("Step Type:N", scale=color_scale, legend=None),
                tooltip=["Step Type", "Count"],
            )
            .properties(height=240, padding={"left": 10})
            .configure_view(strokeWidth=0)
        )
        st.altair_chart(top_chart, width="stretch")

        st.divider()

    # ── Case History ──
    st.markdown("#### Case Execution History")
    history = st.session_state.cases_history

    # Pre-seed with sample data if empty so the dashboard looks alive
    if not history:
        history = [
            {
                "case_id": "a1b2c3d4",
                "client_name": "Sarah Chen",
                "risk_level": "standard",
                "steps_completed": 14,
                "decisions": 3,
                "status": "completed",
                "timestamp": "2026-02-25T09:14:32",
            },
            {
                "case_id": "e5f6g7h8",
                "client_name": "Viktor Petrov",
                "risk_level": "high",
                "steps_completed": 14,
                "decisions": 4,
                "status": "completed",
                "timestamp": "2026-02-25T10:32:15",
            },
            {
                "case_id": "i9j0k1l2",
                "client_name": "Maria Santos",
                "risk_level": "standard",
                "steps_completed": 12,
                "decisions": 3,
                "status": "completed",
                "timestamp": "2026-02-25T14:05:47",
            },
            {
                "case_id": "m3n4o5p6",
                "client_name": "Jean-Pierre Trudeau",
                "risk_level": "high",
                "steps_completed": 14,
                "decisions": 4,
                "status": "completed",
                "timestamp": "2026-02-26T08:45:22",
            },
            {
                "case_id": "q7r8s9t0",
                "client_name": "Aisha Mohammed",
                "risk_level": "standard",
                "steps_completed": 10,
                "decisions": 2,
                "status": "completed",
                "timestamp": "2026-02-26T11:20:08",
            },
            {
                "case_id": "u1v2w3x4",
                "client_name": "Sarah Chen",
                "risk_level": "standard",
                "steps_completed": 14,
                "decisions": 3,
                "status": "completed",
                "timestamp": "2026-02-27T09:05:11",
            },
        ]

    if not history:  # still empty after seeding attempt (shouldn't happen)
        st.info(
            "No cases executed yet. Run cases in the **Execute** tab to see analytics here."
        )
    else:
        # Summary metrics
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Total Cases", len(history))
        completed = sum(1 for c in history if c["status"] == "completed")
        h2.metric("Completed", completed)
        high_risk = sum(1 for c in history if c["risk_level"] == "high")
        h3.metric("High Risk", high_risk)
        avg_steps = round(sum(c["steps_completed"] for c in history) / len(history), 1)
        h4.metric("Avg Steps/Case", avg_steps)

        # Case table
        st.dataframe(
            [
                {
                    "Case ID": c["case_id"],
                    "Client": c["client_name"],
                    "Risk": c["risk_level"],
                    "Steps": c["steps_completed"],
                    "Decisions": c["decisions"],
                    "Status": c["status"].upper(),
                    "Time": c["timestamp"][:19],
                }
                for c in history
            ],
            width="stretch",
        )

    st.divider()

    # ── Training Performance ──
    st.markdown("#### Training Performance")
    total = st.session_state.training_total
    score = st.session_state.training_score
    training_answers = st.session_state.training_answers

    # Pre-seed with sample data using real step names from the selected workflow
    if total == 0 and selected_wf:
        import random as _rng

        quiz_steps = [
            s
            for s in selected_wf.steps.values()
            if s.step_type in (StepType.HUMAN, StepType.DECISION, StepType.AUTO)
        ]
        if quiz_steps:
            _rng.seed(42)  # deterministic
            training_answers = []
            for s in quiz_steps:
                training_answers.append(
                    {"step_title": s.title, "is_correct": _rng.random() > 0.25}
                )
            score = sum(1 for a in training_answers if a["is_correct"])
            total = len(training_answers)
            st.caption(
                "_Showing sample data — complete a training quiz to see your own results_"
            )

    if total == 0:
        st.info("No training sessions completed yet. Run a quiz in the **Train** tab.")
    else:
        t1, t2, t3 = st.columns(3)
        pct = round(score / total * 100)
        t1.metric("Questions Answered", total)
        t2.metric("Correct", score)
        t3.metric("Accuracy", f"{pct}%")
        st.progress(pct / 100)

        # Per-step breakdown as a table
        if training_answers:
            import pandas as pd

            step_results = {}
            for a in training_answers:
                step = a["step_title"]
                if step not in step_results:
                    step_results[step] = {"correct": 0, "total": 0}
                step_results[step]["total"] += 1
                if a["is_correct"]:
                    step_results[step]["correct"] += 1

            table_data = []
            for step_name, r in step_results.items():
                acc = round(r["correct"] / r["total"] * 100)
                table_data.append(
                    {
                        "Step": step_name,
                        "Correct": r["correct"],
                        "Total": r["total"],
                        "Accuracy": f"{acc}%",
                        "Status": "Pass" if acc >= 80 else "Review",
                    }
                )

            st.dataframe(table_data, width="stretch")


# ─────────────────────────────────────────────────────────────────────────────
# Main layout
# ─────────────────────────────────────────────────────────────────────────────

# ── Admin overlay — shown regardless of view ──
if st.session_state.admin_mode:
    render_analytics_tab()

elif st.session_state.app_view == "home":
    # ── Welcome / Landing Page ──

    # ── Hero section ──
    st.markdown(
        """
    <div style="padding: 2.5rem 0 1rem 0;">
        <h2 style="margin:0 0 0.5rem 0; font-size:1.75rem; font-weight:700; letter-spacing:-0.02em;">
            Turn documents into live workflows
        </h2>
        <p style="margin:0; font-size:1.05rem; color:#6B6B6B; line-height:1.6; max-width:720px;">
            Flowline parses process documents into executable, auditable workflows.
            Upload a document, then choose your path below.
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ── Two-path selection cards ──
    path_col1, path_col2 = st.columns(2)

    with path_col1:
        st.markdown(
            """
        <div style="
            background: #ffffff;
            border: 2px solid #E8E8E4;
            border-radius: 16px;
            padding: 2rem;
            height: 100%;
        ">
            <div style="
                width: 48px; height: 48px;
                background: #0A0A0A;
                border-radius: 12px;
                display: flex; align-items: center; justify-content: center;
                font-size: 1.4rem;
                margin-bottom: 1rem;
                color: #ffffff;
            ">&#9654;</div>
            <h3 style="margin:0 0 0.5rem 0; font-size:1.2rem;">Execute Workflow</h3>
            <p style="margin:0 0 1rem 0; font-size:0.9rem; color:#6B6B6B; line-height:1.5;">
                Parse a document, configure tool integrations for each step, then execute
                the workflow with real client data. AI handles routine processing; you handle key decisions.
            </p>
            <div style="display:flex; align-items:center; gap:6px; font-size:0.8rem; color:#999; font-weight:600;">
                Parse <span style="color:#ccc;">›</span>
                Configure <span style="color:#ccc;">›</span>
                Execute
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button(
            "Start Executing",
            type="primary",
            key="go_execute",
            icon=":material/play_arrow:",
            width="stretch",
        ):
            st.session_state.app_view = "execute"
            st.rerun()

    with path_col2:
        st.markdown(
            """
        <div style="
            background: #ffffff;
            border: 2px solid #E8E8E4;
            border-radius: 16px;
            padding: 2rem;
            height: 100%;
        ">
            <div style="
                width: 48px; height: 48px;
                background: #FFC629;
                border-radius: 12px;
                display: flex; align-items: center; justify-content: center;
                font-size: 1.4rem;
                margin-bottom: 1rem;
                color: #0A0A0A;
            ">&#9733;</div>
            <h3 style="margin:0 0 0.5rem 0; font-size:1.2rem;">Train on Workflow</h3>
            <p style="margin:0 0 1rem 0; font-size:0.9rem; color:#6B6B6B; line-height:1.5;">
                Parse a document, then practice with AI-generated compliance scenarios.
                Test your knowledge on every step. No tool configuration needed.
            </p>
            <div style="display:flex; align-items:center; gap:6px; font-size:0.8rem; color:#999; font-weight:600;">
                Parse <span style="color:#ccc;">›</span>
                Train
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button(
            "Start Training",
            type="primary",
            key="go_train",
            icon=":material/school:",
            width="stretch",
        ):
            st.session_state.app_view = "train"
            st.rerun()

    # ── Supported formats strip ──
    st.markdown(
        """
    <div style="
        background: #ffffff;
        border: 1px solid #E8E8E4;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        display: flex;
        align-items: center;
        gap: 2rem;
        margin-top: 1.5rem;
    ">
        <p style="margin:0; font-weight:700; font-size:0.85rem; color:#6B6B6B; text-transform:uppercase; letter-spacing:0.05em; white-space:nowrap;">
            Supported formats
        </p>
        <div style="display:flex; gap:0.75rem; flex-wrap:wrap;">
            <span style="background:#f5f5f3; padding:6px 14px; border-radius:20px; font-size:0.8rem; font-weight:600; color:#0A0A0A;">Text</span>
            <span style="background:#f5f5f3; padding:6px 14px; border-radius:20px; font-size:0.8rem; font-weight:600; color:#0A0A0A;">BPMN</span>
            <span style="background:#f5f5f3; padding:6px 14px; border-radius:20px; font-size:0.8rem; font-weight:600; color:#0A0A0A;">Visio</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
    <p style="color:#6B6B6B; font-size:0.875rem; margin-top:1rem;">
        Select a document format in the sidebar and click <strong>Parse Document</strong> to get started.
    </p>
    """,
        unsafe_allow_html=True,
    )

elif st.session_state.app_view == "execute":
    # ══════════════════════════════════════════════════════════════════════════
    # EXECUTE VIEW — Parse → Configure → Execute
    # ══════════════════════════════════════════════════════════════════════════

    # ── Top bar: home + segmented toggle (right-aligned) ──
    tb1, tb2, tb3, tb4 = st.columns([1.2, 5.8, 1.5, 1.5])
    with tb1:
        if st.button("Home", key="exec_home", type="tertiary", icon=":material/home:"):
            st.session_state.app_view = "home"
            st.rerun()
    with tb2:
        pass
    with tb3:
        st.button(
            "Execute",
            key="toggle_exec_active",
            type="primary",
            disabled=True,
            use_container_width=True,
        )
    with tb4:
        if st.button(
            "Train", key="toggle_to_train", type="secondary", use_container_width=True
        ):
            st.session_state.app_view = "train"
            st.rerun()

    # ── Pipeline Stepper Banner ──
    p_step = st.session_state.pipeline_step
    has_wf = st.session_state.workflow is not None
    has_cfg = st.session_state.configs_saved

    step1_cls = "done" if has_wf else ("active" if p_step == 1 else "")
    step2_cls = "done" if has_cfg else ("active" if has_wf and p_step <= 2 else "")
    step3_cls = "active" if has_cfg and p_step >= 3 else ""

    s1_icon = "✓" if has_wf else "1"
    s2_icon = "✓" if has_cfg else "2"
    s3_icon = "3"

    st.markdown(
        f"""
    <div class="pipeline-stepper">
        <div class="ps-step {step1_cls}">
            <span class="ps-num">{s1_icon}</span>
            Parse
        </div>
        <span class="ps-arrow">›</span>
        <div class="ps-step {step2_cls}">
            <span class="ps-num">{s2_icon}</span>
            Configure
        </div>
        <span class="ps-arrow">›</span>
        <div class="ps-step {step3_cls}">
            <span class="ps-num">{s3_icon}</span>
            Execute
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ── Tab selector (session-state driven for programmatic switching) ──
    _atab = st.session_state.active_exec_tab
    _tcol1, _tcol2, _tcol3 = st.columns(3)
    with _tcol1:
        _t1_type = "primary" if _atab == "parse" else "secondary"
        if st.button(
            "1. Parse", key="tab_btn_parse", type=_t1_type, use_container_width=True
        ):
            st.session_state.active_exec_tab = "parse"
            st.rerun()
    with _tcol2:
        _t2_type = "primary" if _atab == "configure" else "secondary"
        if st.button(
            "2. Configure",
            key="tab_btn_configure",
            type=_t2_type,
            use_container_width=True,
        ):
            st.session_state.active_exec_tab = "configure"
            st.rerun()
    with _tcol3:
        _t3_type = "primary" if _atab == "execute" else "secondary"
        if st.button(
            "3. Execute", key="tab_btn_execute", type=_t3_type, use_container_width=True
        ):
            st.session_state.active_exec_tab = "execute"
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if _atab == "parse":
        render_parse_tab()
    elif _atab == "configure":
        render_configure_tab()
    else:
        render_execute_tab()

elif st.session_state.app_view == "train":
    # ══════════════════════════════════════════════════════════════════════════
    # TRAIN VIEW — Parse → Train
    # ══════════════════════════════════════════════════════════════════════════

    # ── Top bar: home + segmented toggle (right-aligned) ──
    tb1, tb2, tb3, tb4 = st.columns([1.2, 5.8, 1.5, 1.5])
    with tb1:
        if st.button("Home", key="train_home", type="tertiary", icon=":material/home:"):
            st.session_state.app_view = "home"
            st.rerun()
    with tb2:
        pass
    with tb3:
        if st.button(
            "Execute", key="toggle_to_exec", type="secondary", use_container_width=True
        ):
            st.session_state.app_view = "execute"
            st.rerun()
    with tb4:
        st.button(
            "Train",
            key="toggle_train_active",
            type="primary",
            disabled=True,
            use_container_width=True,
        )

    # ── Tab selector (session-state driven — matches Execute style) ──
    _ttab = st.session_state.active_train_tab
    _ttcol1, _ttcol2 = st.columns(2)
    with _ttcol1:
        _tt1_type = "primary" if _ttab == "parse" else "secondary"
        if st.button(
            "1. Parse",
            key="train_tab_btn_parse",
            type=_tt1_type,
            use_container_width=True,
        ):
            st.session_state.active_train_tab = "parse"
            st.rerun()
    with _ttcol2:
        _tt2_type = "primary" if _ttab == "train" else "secondary"
        if st.button(
            "2. Train",
            key="train_tab_btn_train",
            type=_tt2_type,
            use_container_width=True,
        ):
            st.session_state.active_train_tab = "train"
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if _ttab == "parse":
        render_parse_tab()
    else:
        render_train_tab()
