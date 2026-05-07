# 🔖 Glossa

> **Marginalia for the AI age.** Source-grounded answers with citations — at zero per-token cost.

Glossa is a thin, opinionated CLI on top of [NotebookLM](https://notebooklm.google.com). You feed it your documents once, then ask questions; it answers with citations back to the source. No per-token billing, no model selection, no prompt engineering — just **glossa**: marginal commentary anchored to authoritative text.

```bash
pip install glossa-lm
glossa notebook init ./docs ./README.md
glossa ask "What does the project do?"
```

---

## Why "Glossa"?

In medieval scholastic tradition, a *glossa* was the explanatory note written in the margin of an authoritative text — never replacing the text, always anchored to it. That's exactly what NotebookLM does: it reads your sources and writes the margin, with citations back to the page.

Glossa (the tool) is the CLI that makes this practice programmatic and project-shaped: one persistent notebook per project, hash-based source sync, scriptable Q&A.

---

## Status

**Alpha (v0.1).** Single-purpose: ask source-grounded questions from the command line. No streaming, no agent loop, no fancy orchestration. Stateless by design.

---

## Install

```bash
pip install glossa-lm
```

You also need [`notebooklm-py`](https://github.com/teng-lin/notebooklm-py) installed and authenticated:

```bash
pip install notebooklm-py
notebooklm login
```

---

## Quick start

```bash
# 1. Initialize a notebook for this project (one-time, ~30s–10min depending on source count)
glossa notebook init ./docs ./README.md ./prompts/

# 2. Ask. Source-grounded answer + citations.
glossa ask "How does the auth flow handle expired tokens?"

# 3. After editing files, re-sync (hash-based — only changed files re-uploaded)
glossa notebook sync

# 4. Inspect notebook state
glossa notebook status
```

Notebook ID and source hashes are cached in `.glossa/` (gitignored).

---

## How it differs from a normal LLM CLI

| | Generative LLM CLI | Glossa |
|---|---|---|
| Input | Free prompt | Source corpus + question |
| Output | Whatever the model generates | Answer grounded in *your* sources, with citations |
| Cost | Per-token, scales with usage | $0 (your Google account quota) |
| Hallucination | Possible | Citation pressure dramatically reduces it |
| Best for | Code generation, conversation, brainstorm | Document Q&A, synthesis, research |

If you need code generation, debugging, or freeform reasoning — use a normal LLM (or **[RUNE](https://github.com/neurabytelabs/rune)**, our cousin project for Spinoza-grounded prompt amplification). Glossa is for the other half of the work: *answering from what already exists*.

---

## CLI reference

```
glossa notebook init [PATHS...]   # create notebook, add sources, wait for indexing
glossa notebook sync              # hash-based incremental sync
glossa notebook status            # notebook ID + source readiness
glossa ask "question"             # source-grounded Q&A
glossa ask "..." --json           # machine-readable: {answer, references, ...}
glossa ask "..." --show-sources   # print citations alongside the answer
```

---

## Limitations (be honest)

- **Setup is not instant.** Each source takes 30s–10min to index in NotebookLM.
- **No streaming.** NotebookLM's chat is sync.
- **No system prompts, no temperature, no max_tokens.** You get what NotebookLM gives.
- **Auth is browser-based OAuth** (`notebooklm login`). Sessions can expire; re-login required.
- **Generation features (audio/video/quiz) are out of scope** — Glossa focuses on Q&A only. Use `notebooklm` CLI directly for those.

---

## Roadmap (post v0.1)

- Source watchers (auto-sync on file change)
- Citation rendering (terminal-friendly inline footnotes)
- `glossa serve` — minimal HTTP wrapper for editor integrations
- Multi-notebook support (per-domain knowledge bases)

---

## Project family

Glossa is a sibling project to **[RUNE](https://github.com/neurabytelabs/rune)** under [NeuraByte Labs](https://github.com/neurabytelabs):

- **RUNE** — *Generation*: 8-layer Spinoza-grounded prompt amplification
- **Glossa** — *Citation*: source-grounded Q&A with NotebookLM

They share no code. They share a worldview: every text deserves to be taken seriously.

---

## License

MIT © 2026 NeuraByte Labs / Mustafa Saraç
