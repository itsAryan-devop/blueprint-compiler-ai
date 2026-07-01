# Blueprint Compiler

**An English prompt → a validated, self-repairing, executable application blueprint.**

A compiler-style system that turns a one-line app description into a strict JSON
blueprint (UI · API · Database · Auth · Business Logic) and **stands up a live
FastAPI server backed by a real SQLite database** for every generated app.

> **🌐 Live demo:** [`blueprint-compiler-ai.onrender.com`](https://blueprint-compiler-ai.onrender.com)
> *(Render free instance — sleeps after 15 min; first request after sleep takes ~30s.)*

```
English prompt
   │
   ▼
[1] Intent extraction    →  features, roles, assumptions
[2] System design        →  entities, flows, business rules
[3] Schema generation    →  UI · API · Database · Auth · Business logic
[4] Validate + repair    →  cross-layer consistency, deterministic auto-fix
[5] Live runtime         →  real SQLite tables + mounted FastAPI routes
   │
   ▼
Validated blueprint + executable app
```

---

## Why it's built like a compiler (not "one big prompt")

A compiler refuses to emit broken output. It works in **passes** — lex → parse →
type-check → emit — and any pass can reject the input with a precise location.
This project mirrors that for app generation:

- **Strict typed contracts** (Pydantic v2 with `extra="forbid"`) at every stage
  boundary. The LLM cannot hallucinate a field that isn't in the schema.
- **Five passes, never one prompt.** Each pass solves one small problem and
  hands a typed object to the next. Easy to debug, easy to repair.
- **Cross-layer validation** runs over the final blueprint: every UI field
  resolves to an API field, every API field resolves to a DB column, every
  role used in business logic exists in Auth.
- **Tiered repair** when validation fails: a deterministic code-only fix runs
  first; only when that's not safe does it ask the LLM to regenerate **only the
  broken layer** (never a blind retry).
- **Provable execution.** The runtime takes the JSON and creates real SQLite
  tables + live FastAPI routes with auth enforced — every compile gives you a
  Swagger URL you can poke immediately.

---

## What's in the repo

| Mandatory deliverable                | Where it lives                                     |
|--------------------------------------|----------------------------------------------------|
| Multi-stage pipeline (4+ passes)     | `pipeline/`                                        |
| Strict schema enforcement (Pydantic) | `contracts/` (`extra="forbid"` on every model)     |
| Validation + Repair engine           | `validation/`, `repair/`                           |
| Deterministic behaviour              | `temperature=0` + byte-exact on-disk cache (`llm/cache.py`) |
| Execution awareness                  | `runtime/` — real SQLite + live FastAPI            |
| Failure handling                     | `pipeline/input_analysis.py` (Phase 8 analyzer)    |
| Evaluation framework                 | `eval/` — 20-prompt dataset, runner, metrics       |
| Cost vs quality                      | `run_cost_quality.py` (Groq-only vs Gemini-only)   |
| Frontend + deploy                    | `app/`, `Dockerfile`, `.dockerignore`              |

---

## Tech stack

| Concern              | Choice                                              |
|----------------------|-----------------------------------------------------|
| Language             | Python 3.11                                         |
| Contracts            | Pydantic v2                                         |
| Web framework        | FastAPI                                             |
| LLM (primary)        | Groq (`llama-3.3-70b-versatile`) — high throughput  |
| LLM (backup)         | Google Gemini (`gemini-2.5-flash`) — higher quality |
| Runtime DB           | SQLite                                              |
| Tests                | pytest (unit + integration tests)                |
| Deploy               | Docker → Render / Railway / Cloud Run               |

**Provider abstraction with multi-key rotation:** `llm/client.py` holds a pool
of comma-separated keys per provider. A key that hits its daily/per-minute cap
is skipped instantly via a per-process circuit breaker. A hard wall-clock
timeout (via `concurrent.futures`) force-cancels any single call that takes
more than 25 s, so a stuck request can never hang the live URL.

---

## Live demo prompts to try

| Try this in the live URL                                                                                                    | What to look for in the JSON         |
|-----------------------------------------------------------------------------------------------------------------------------|--------------------------------------|
| `Build a CRM with login, contacts, and an admin-only analytics page.`                                                       | clean blueprint, validation issues=0 |
| `Small e-commerce store: products, cart, orders, customers, and an admin dashboard.`                                        | products / orders / customers tables |
| `Build a hospital patient portal with appointments, prescriptions, and lab results. Add HIPAA-style audit logs.`            | 3 roles + `audit_logs` table         |
| `Make me an app.`                                                                                                           | `diagnosis.severity = "vague"` + 3 auto-assumptions |
| `Build a notes app with no login or users, but also add admin-only sharing and role-based permissions.`                     | `diagnosis.severity = "conflicting"` + resolution   |
| *(empty submission)*                                                                                                        | `needs_clarification: true` — no LLM call wasted    |

Each response includes a **`runtime.docs_url`** — click it to see the
generated app's interactive Swagger UI and call its endpoints live.

---

## Local setup

```bash
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env       # paste your free Gemini + Groq keys
venv\Scripts\python.exe verify_setup.py
```

Get free keys at: **https://aistudio.google.com/app/apikey** and
**https://console.groq.com/keys**. Multiple comma-separated keys are supported
out of the box (recommended — Gemini's free tier is ~20 requests/day per key).

### Run the web server

```bash
venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# open http://localhost:8000
```

### Run the tests

```bash
venv\Scripts\python.exe -m pytest tests/ -q       # unit + integration, no network
```

### Run the eval suite

```bash
venv\Scripts\python.exe run_eval.py               # all 20 prompts
venv\Scripts\python.exe run_eval.py --subset 4    # quick check
```

The eval writes `eval_metrics.json` with per-case outcome, latency, repair
counts, and assumptions. Results depend on your available free-tier quota — a
run with exhausted keys will show timeouts, which is itself honest signal about
free-tier limits rather than a code failure.

### Cost vs quality comparison

```bash
venv\Scripts\python.exe run_cost_quality.py --subset 3
```

Pins the same prompts to each provider and prints a side-by-side table.

---

## Run with Docker

The image is **slim, secret-free, and layer-cached**. API keys are injected at
runtime — **never baked in**.

```bash
docker build -t blueprint-compiler .

docker run --rm -p 8000:8000 \
  -e GEMINI_API_KEYS="$GEMINI_API_KEYS" \
  -e GROQ_API_KEYS="$GROQ_API_KEYS" \
  -e LLM_PRIMARY=groq \
  -v blueprint-data:/data \
  blueprint-compiler

# health check
curl http://localhost:8000/healthz
```

The same image deploys to **Render / Railway / Cloud Run**: connect the repo,
the host detects the `Dockerfile`, paste the same env vars into its secrets UI.
Mount a volume at `/data` to persist the LLM response cache and generated
SQLite databases across container replacements.

---

## Project layout

```
contracts/    Pydantic models — the strict contracts every pipeline stage must satisfy
pipeline/     The 5 compiler passes (intent, design, schema_gen, refine, input_analysis)
validation/   Structural + cross-layer consistency checkers
repair/       Tiered repair engine (deterministic → targeted LLM regen → honest failure)
runtime/      Blueprint → real SQLite tables + live FastAPI routes with auth
llm/          Provider abstraction (Gemini / Groq), key rotation, circuit breaker, cache
eval/         20-prompt dataset, runner, per-case metrics
app/          The deployed FastAPI server + frontend
tests/        unit + integration tests (zero network calls)
Dockerfile    Production image — slim, layered, secret-free
```

---

## Key engineering decisions

**Why Pydantic with `extra="forbid"`?**
A single setting that turns "the LLM hallucinated an extra field" from a silent
bug into an instantly catchable error with a precise path. The repair engine
uses Pydantic's own error locations to delete or fix the offending node.

**Why multi-stage instead of one big prompt?**
Each stage's prompt embeds only that stage's schema (~2 kB) instead of the
whole 12 kB blueprint schema. The LLM has fewer ways to go wrong, every output
is independently checkable, and a failure in stage 4 doesn't waste stages 1–3.

**Why a wall-clock timeout in addition to the SDK's HTTP timeout?**
The Google/Groq SDKs do their own retries inside a single `generate_content`
call. Their "timeout" only bounds one HTTP attempt, not the retry loop, so a
stuck call can grind for minutes. We wrap each call in
`concurrent.futures.ThreadPoolExecutor + future.result(timeout=25s)` to
*force-cancel* and fail over.

**Why Groq is primary, not Gemini?**
Gemini's free tier is ~20 requests/day per key. For a live URL a reviewer
might hit a dozen times, that's not enough. Groq has ~14,400 requests/day per
key and is built for speed. Gemini stays as the smarter fallback for cases
where Groq's output fails validation.

**Why deterministic repair before LLM regen?**
Auto-fixable issues (unknown role → drop it, missing permission → define it,
unenforced role-access rule → enforce it, plural/case name mismatch → normalize
it) get fixed for free in code with zero LLM calls. Only when an issue can't be
mechanically resolved does the engine ask the LLM to regenerate the single
broken layer — never a blind full retry. Run `python run_eval.py` to see the
deterministic-vs-LLM repair split on your own quota.

---

## Honest limitations

- **Cold start on the live URL is ~30 s** (Render free tier sleeps after 15 min
  idle). Hit `/healthz` first to wake it before a demo.
- **Generated `/login` endpoints are demo-grade** — they echo a fake token. A
  real deploy would wire up real password hashing and JWTs.
- **Free-tier quota is a hard ceiling.** With 7+ keys in rotation it's enough
  for casual use, but a sustained load eventually 429s every key — the system
  fails gracefully (visible logging, structured error) rather than hanging.
- **The runtime currently writes any payload key that matches a real DB
  column.** It does not yet validate against the API's declared `request_fields`
  — a follow-up tightening, not a correctness issue.
- **Determinism is exact on a cache hit** (same prompt → byte-identical JSON via
  the on-disk cache). On a genuine cache miss, `temperature=0` makes generation
  *near*-deterministic, but provider fallback (Groq → Gemini) can change wording;
  the cache is what guarantees reproducibility for a given prompt.
- **On a live cache miss, expect 30–90 s** while the 5 stages run. If every
  free-tier key is exhausted the request returns an honest 502 asking you to
  retry — the system never falls back to a canned template that ignores your
  prompt.

---

## Submission summary

| Deliverable     | Status                                                                                |
|-----------------|---------------------------------------------------------------------------------------|
| Live URL        | ✅ [blueprint-compiler-ai.onrender.com](https://blueprint-compiler-ai.onrender.com)  |
| GitHub repo     | ✅ [itsAryan-devop/blueprint-compiler-ai](https://github.com/itsAryan-devop/blueprint-compiler-ai) |
| Tests           | ✅ passing (`python -m pytest tests/ -q`)                                            |
| Eval framework  | ✅ `python run_eval.py` — 20-prompt dataset + metrics, reproducible on your keys     |
