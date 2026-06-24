# AI Compiler for Software Generation

Turn a plain-English app request into a **strict, validated, self-repairing,
runnable** configuration — the way a compiler turns source code into a working
program. This is not a single AI prompt: it is a staged, checked, reliable
system with the LLM as one small, untrusted component inside it.

```
English prompt -> intent -> design -> schemas -> validate + repair -> runnable config
```

## Why it's built like a compiler
A compiler works in *passes* (lex -> parse -> check -> emit) and refuses to
produce broken output. We mirror that: each stage is small, typed, and
independently checkable, so errors are caught early and repaired surgically
instead of regenerating everything and hoping.

## Tech stack
| Concern              | Choice                            |
|----------------------|-----------------------------------|
| Language             | Python 3.11                       |
| Contracts            | Pydantic v2                       |
| Backend + runtime    | FastAPI                           |
| LLM (primary)        | Google Gemini (Flash, free tier)  |
| LLM (backup/compare) | Groq (free tier)                  |
| Runtime DB           | SQLite                            |

## Project layout
```
contracts/   Pydantic models — the contracts every stage must satisfy
pipeline/    the four compiler passes: intent, design, schema_gen, refine
validation/  structural + cross-layer validators
repair/      the tiered repair engine
runtime/     config -> real SQLite tables + live FastAPI routes
llm/         provider abstraction (Gemini / Groq), JSON mode, temp 0, retries
eval/        20-prompt dataset + runner + metrics
app/         FastAPI server + responsive compiler workbench
tests/       unit + integration tests
```

## Setup
```
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env      # then paste your free keys into .env
venv\Scripts\python.exe verify_setup.py
```
If you see a reply from both Gemini and Groq, the foundation works.

## Run locally
```
venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

The workbench shows the generated architecture, validation and repair evidence,
downloadable JSON, and a link to the app's live FastAPI runtime and interactive
API documentation.

For reliable demos, the web workbench uses the fast deterministic compiler path
by default, then still runs validation, targeted repair, SQLite generation, and
runtime mounting. To run the full live LLM pipeline from the web endpoint, set
`WEB_COMPILER_MODE=live` before starting Uvicorn.

## Run with Docker
The image is **slim, secret-free, and layer-cached**. Keys are injected at
runtime via environment variables -- never baked into the image.

```
# build (uses .dockerignore to exclude .env, venv, caches, tests)
docker build -t ai-compiler .

# run -- pass the API key pools the rotation needs (comma-separated)
docker run --rm -p 8000:8000 \
  -e GEMINI_API_KEYS="$GEMINI_API_KEYS" \
  -e GROQ_API_KEYS="$GROQ_API_KEYS" \
  -v ai-compiler-data:/data \
  ai-compiler

# then visit http://localhost:8000
# health check: curl http://localhost:8000/healthz
```

The same image deploys on **Render / Railway / Google Cloud Run**. Build from
the root `Dockerfile`, expose the host-assigned `PORT`, and inject
`GEMINI_API_KEYS` / `GROQ_API_KEYS` through the host's secrets UI. Mount
persistent storage at `/data` when generated runtimes and the LLM cache must
survive container replacement.

## Status
- [x] Phase 0 — setup + provider connectivity
- [x] Phase 1 — Pydantic contracts
- [x] Phase 2 — walking skeleton (English -> one LLM call -> validated blueprint)
- [x] Phase 3 — four-stage pipeline (intent -> design -> schemas -> refine, modular)
- [x] Phase 4 — validation layer (structural + cross-layer)
- [x] Phase 5 — repair engine (tiered: deterministic + targeted regen + repair log)
- [x] Phase 6 — determinism (temperature 0 + response caching; same-prompt-5x proof)
- [x] Phase 7 — runtime (blueprint -> real SQLite tables + live FastAPI routes with auth enforced)
- [x] Phase 8 — failure handling (vague / conflicting / empty prompts -> clarify or assume-and-record)
- [x] Phase 9 — evaluation framework (20-prompt dataset + runner + metrics)
- [x] Phase 10 — cost vs quality (provider pin: gemini-only vs groq-only comparison)
- [x] Phase 11 — responsive frontend + executable runtimes + production Docker package
- [ ] Phase 12 — polish + Loom video + submit
