# Flowline

**AI-Native SOP Execution Engine** - Parse, execute, and train on Standard Operating Procedures.

---

## What it does

SOPs exist in three formats across any regulated organization:

| Format | Tool | How we parse it |
|--------|------|-----------------|
| **Text SOP** | Word, PDF, wiki | LLM (GPT-4o) extracts steps, decisions, and connections |
| **BPMN** | Camunda, Signavio, Bizagi | XML parsing — tasks, gateways, sequence flows, swimlanes |
| **Visio** | Microsoft Visio (.vsdx) | ZIP + XML extraction — shapes, connections, containers |

All three converge to the **same workflow graph** → same executor → same training mode.

### Three modes

1. **Parse** — Upload any SOP format, get an executable workflow graph
2. **Execute** — Run a real client case through the workflow step-by-step (AI handles AUTO steps, humans handle HUMAN steps)
3. **Train** — Practice with AI-generated compliance scenarios and quizzes

## Architecture

The engine is provider-agnostic. A single factory (`engine/llm.py`) handles both standard OpenAI and Azure OpenAI — set `OPENAI_API_KEY` or `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` and the rest of the codebase doesn't care which provider is behind it.

BPMN and Visio parsing require zero LLM calls — pure deterministic parsing.

## Quick start

```bash
# Clone and set up
git clone <repo-url> && cd sop-autopilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Graphviz (system dependency for workflow visualization)
brew install graphviz  # macOS

# Configure API key (supports OpenAI or Azure OpenAI)
cp .env.example .env
# Edit .env — uncomment and fill in your preferred provider

# Generate sample Visio file
python tools/create_sample_visio.py

# Run
streamlit run app.py
```

## Project structure

```
sop-autopilot/
├── app.py                          # Streamlit UI — Parse, Execute, Train views
├── engine/
│   ├── llm.py                      # LLM client factory (OpenAI / Azure OpenAI)
│   ├── models.py                   # Shared data models (Workflow, Step, CaseState)
│   ├── parser_text.py              # LLM-based text SOP → workflow parser
│   ├── parser_bpmn.py              # BPMN 2.0 XML parser (no LLM)
│   ├── parser_visio.py             # Visio .vsdx ZIP+XML parser (no LLM)
│   ├── executor.py                 # Workflow state machine + LLM auto-execution
│   └── training.py                 # Training scenario + quiz generation via LLM
├── prompts/                        # System prompts for LLM calls
├── data/                           # Sample SOPs and mock client data
├── tools/
│   └── create_sample_visio.py      # Generates a sample .vsdx file
└── requirements.txt
```

## The regulatory basis

This demo uses FINTRAC Client Identity Verification — the actual Canadian regulation that fintechs must follow as registered securities dealers.

The critical human-only decision: confirming a client identity carries regulatory accountability under FINTRAC. AI can gather documents, run screenings, and flag risks — but the final identity confirmation must remain human because the reporting entity bears legal responsibility for compliance.

