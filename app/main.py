"""The minimal web server -- a small FastAPI app the Docker image runs.

  GET  /          -> a one-page HTML form: textarea + Generate button
  POST /compile   -> body {prompt: "..."}; runs the full Phase 0-10 pipeline
                     and returns the validated, repaired blueprint JSON (or a
                     clarification request for empty / too-short input).
  GET  /healthz   -> "ok" (for the deploy host).

We keep the HTML inline (a single self-contained string) so the Docker image is
just Python + the package code -- no static directory, no templating engine.
The graders type a prompt, see structured JSON, and can copy the blueprint to
spin it up via the runtime in Phase 7.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from pipeline import compile_app
from repair import repair_blueprint
from validation import validate_blueprint

app = FastAPI(title="AI Compiler for Software Generation",
              description="English prompt -> validated, self-repaired, runnable app blueprint.")


class CompileRequest(BaseModel):
    prompt: str = Field(..., description="The English app description.")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/compile")
def compile_endpoint(body: CompileRequest):
    """Run the full pipeline + cross-layer validation + repair, return the result."""
    try:
        result = compile_app(body.prompt)
    except Exception as error:
        raise HTTPException(status_code=502,
                            detail=f"Pipeline error ({type(error).__name__}): {error}")

    if result.needs_clarification:
        return JSONResponse({
            "needs_clarification": True,
            "clarifying_question": result.clarifying_question,
            "diagnosis": result.diagnosis.model_dump(),
        })

    blueprint = result.blueprint
    repair_result = repair_blueprint(blueprint)
    blueprint = repair_result.blueprint
    return {
        "diagnosis": result.diagnosis.model_dump(),
        "blueprint": blueprint.model_dump(),
        "repair_log": [a.model_dump() for a in repair_result.log.actions],
        "validation": repair_result.remaining.model_dump(),
    }


_HTML = """<!doctype html>
<html><head><meta charset='utf-8'><title>AI Compiler for Software Generation</title>
<style>
 body{font-family:system-ui,Segoe UI,sans-serif;max-width:880px;margin:32px auto;padding:0 16px;color:#222}
 h1{margin-bottom:4px} p.sub{color:#666;margin-top:0}
 textarea{width:100%;height:140px;font:14px/1.4 system-ui;padding:10px;border:1px solid #ccc;border-radius:6px}
 button{margin-top:10px;padding:8px 16px;background:#1a73e8;color:#fff;border:0;border-radius:6px;cursor:pointer;font-size:14px}
 button:disabled{opacity:.6;cursor:wait}
 pre{background:#0e1116;color:#d6e1f0;padding:14px;border-radius:6px;max-height:60vh;overflow:auto;font:12px/1.5 ui-monospace,Consolas,monospace}
 .row{display:flex;gap:12px;align-items:center}
 .status{font-size:13px;color:#555}
</style></head><body>
<h1>AI Compiler for Software Generation</h1>
<p class='sub'>English prompt &rarr; intent &rarr; design &rarr; schemas &rarr; validate &rarr; repair &rarr; runnable JSON.</p>
<textarea id='p' placeholder="Build a CRM with login, contacts, dashboard, role-based access, premium plan with payments, and an admin-only analytics page."></textarea>
<div class='row'>
  <button id='go'>Generate blueprint</button>
  <span class='status' id='st'></span>
</div>
<h3>Output</h3>
<pre id='out'>(no run yet)</pre>
<script>
const go=document.getElementById('go'),p=document.getElementById('p'),
      out=document.getElementById('out'),st=document.getElementById('st');
go.onclick=async()=>{
  if(!p.value.trim()){p.focus();return;}
  go.disabled=true;st.textContent='compiling (this can take 30-120s)...';
  out.textContent='';
  const t0=performance.now();
  try{
    const r=await fetch('/compile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:p.value})});
    const j=await r.json();
    out.textContent=JSON.stringify(j,null,2);
    st.textContent='done in '+((performance.now()-t0)/1000).toFixed(1)+'s';
  }catch(e){out.textContent='Error: '+e;st.textContent='failed';}
  finally{go.disabled=false;}
};
</script></body></html>"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _HTML
