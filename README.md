# Cliffhanger Auditor

Script-stage quality check for vertical microdramas. For every episode it scores the **opening hook** (first ~15 s) and the **closing cliffhanger** (last ~20 s), flags weak episodes (with a stricter threshold around the paywall episode), and suggests a rewrite of the final beat.

Built for Kuku AI Generalist Assignment, Problem 3.

## Features
- Upload, paste, or select a sample timestamped screenplay
- LLM judge with keyword rules running alongside; large disagreements are flagged `HUMAN_CHECK`
- Flags: `WEAK_CLIFFHANGER`, `WEAK_HOOK`, `PAYWALL_RISK`, `HUMAN_CHECK`
- Swappable model: Groq, Google Gemini, any OpenAI-compatible API, Anthropic, local Claude CLI, or rules only
- CSV / JSON export

## Quick start
```bash
pip install -r requirements.txt
cp .env.example .env        # add GROQ_API_KEY and/or GEMINI_API_KEY
streamlit run app.py
```

CLI:
```bash
python run.py inputs/show_contract_bride.txt --provider groq --out outputs/run
python run.py inputs/show_contract_bride.txt --labels inputs/labels_contract_bride.csv --provider none
```
Options: `--provider groq|gemini|openai|anthropic|claude_cli|none`, `--model <id>`, `--paywall <n>`, `--labels <csv>` (prints precision/recall), `--out <dir>`.

## Configuration
| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | Default provider. If unset, the first provider with a key is used (Groq, then Gemini, then the rest). |
| `LLM_MODEL` | Model override. Defaults: Groq `openai/gpt-oss-120b`, Gemini `gemini-3.5-flash`. |
| `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `ANTHROPIC_API_KEY` | Provider credentials. |

## Deploy (Streamlit Community Cloud)
1. Push this repo to GitHub (`.env` is git-ignored).
2. On share.streamlit.io, create an app from the repo with `app.py` as the entry point.
3. Under **Settings → Secrets**, add your keys (see `.streamlit/secrets.toml.example`):
   ```toml
   GROQ_API_KEY = "..."
   GEMINI_API_KEY = "..."
   ```

## Script format
```
EPISODE 1: Title
[00:00] INT. BALLROOM - NIGHT. A glass shatters.
[00:02] VICTORIA: You dare wear my mother's necklace?
```
Each episode starts with `EPISODE <n>`. Beats start with `[mm:ss]`. Lines without a timestamp are added to the previous beat.

## Project structure
```
app.py               Streamlit frontend
run.py               CLI and evaluation against labels
auditor/parse.py     Screenplay parsing into episodes and timestamped beats
auditor/llm.py       Provider-agnostic LLM client with retries
auditor/audit.py     Rule scoring, batched LLM judge, flag logic
inputs/              Synthetic test shows and labels
outputs/             Raw outputs from evaluation runs
docs/                Solution write-up (PDF and HTML source)
```
