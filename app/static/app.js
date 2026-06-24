const examples = {
  crm: "Build a CRM with login, contacts, dashboard, role-based access, premium plan with payments, and an admin-only analytics page.",
  marketplace: "Create a two-sided marketplace where sellers list products, customers place orders and reviews, and admins moderate listings. Include Stripe-style payment records and order status rules.",
  clinic: "Build a clinic portal for patients, doctors, and receptionists. Patients book appointments, doctors add visit notes, and receptionists manage schedules. Medical notes must be restricted to doctors.",
};

const $ = (id) => document.getElementById(id);
const promptInput = $("prompt");
const compileButton = $("compile");
const statusRegion = $("status-region");
const results = $("results");
let currentResult = null;
let timer = null;
let startedAt = 0;
let stepTimer = null;

/* ── Pipeline step animation ─────────────────────────────────── */
const pipelineSteps = [
  { id: "step-intent",   title: "Extracting intent",         detail: "Parsing features, roles, and requirements from your prompt." },
  { id: "step-design",   title: "Designing system",          detail: "Defining entities, relationships, flows, and access rules." },
  { id: "step-schema",   title: "Generating schemas",        detail: "Building UI, API, database, and auth configurations." },
  { id: "step-validate", title: "Validating + repairing",    detail: "Running cross-layer checks and targeted repairs." },
  { id: "step-runtime",  title: "Launching runtime",         detail: "Creating SQLite tables and mounting live FastAPI routes." },
];

function resetPipelineSteps() {
  pipelineSteps.forEach(({ id }) => {
    const el = $(id);
    if (el) { el.classList.remove("active", "done"); }
  });
}

function animatePipelineSteps() {
  resetPipelineSteps();
  let currentStep = 0;
  stepTimer = setInterval(() => {
    if (currentStep > 0) {
      const prev = $(pipelineSteps[currentStep - 1].id);
      if (prev) { prev.classList.remove("active"); prev.classList.add("done"); }
    }
    if (currentStep < pipelineSteps.length) {
      const step = pipelineSteps[currentStep];
      const el = $(step.id);
      if (el) el.classList.add("active");
      $("status-title").textContent = step.title;
      $("status-detail").textContent = step.detail;
      currentStep++;
    } else {
      clearInterval(stepTimer);
      stepTimer = null;
    }
  }, 3200);
}

function stopPipelineAnimation(success) {
  clearInterval(stepTimer);
  stepTimer = null;
  if (success) {
    pipelineSteps.forEach(({ id }) => {
      const el = $(id);
      if (el) { el.classList.remove("active"); el.classList.add("done"); }
    });
  } else {
    resetPipelineSteps();
  }
}

/* ── Helpers ─────────────────────────────────────────────────── */
function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setStatus(active, title = "", detail = "") {
  statusRegion.hidden = !active;
  if (!active) {
    clearInterval(timer);
    return;
  }
  $("status-title").textContent = title;
  $("status-detail").textContent = detail;
  startedAt = performance.now();
  $("elapsed").textContent = "0s";
  clearInterval(timer);
  timer = setInterval(() => {
    $("elapsed").textContent = `${Math.floor((performance.now() - startedAt) / 1000)}s`;
  }, 1000);
}

function metric(value, label) {
  return `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function layer(title, content) {
  return `<article class="layer"><h3>${escapeHtml(title)}</h3><p>${content}</p></article>`;
}

function names(items, fallback = "None") {
  return items?.length ? items.map((item) => escapeHtml(item.name ?? item)).join(", ") : fallback;
}

/* ── Result rendering ────────────────────────────────────────── */
function renderResult(data) {
  const bp = data.blueprint;
  const issues = data.validation?.issues ?? [];
  const repairs = data.repair_log ?? [];
  const roles = bp.auth?.roles ?? [];
  const rules = bp.business_logic?.rules ?? [];

  currentResult = data;
  $("result-title").textContent = bp.app_name;
  $("result-type").textContent = bp.app_type;
  $("runtime-link").href = data.runtime.docs_url;
  $("runtime-link").textContent = "Open live API";
  $("metrics").innerHTML =
    metric(bp.ui?.pages?.length ?? 0, "UI pages") +
    metric(bp.api?.endpoints?.length ?? 0, "API endpoints") +
    metric(bp.database?.tables?.length ?? 0, "Database tables") +
    metric(roles.length, "Auth roles") +
    metric(rules.length, "Business rules");

  const assumptions = bp.assumptions ?? [];
  $("summary-panel").innerHTML = `<div class="layer-grid">
    ${layer("Runtime ready", `<strong class="ok">Executable</strong><br>SQLite database and FastAPI routes mounted at <strong>${escapeHtml(data.runtime.base_url)}</strong>.`)}
    ${layer("Validation", `<strong class="${issues.length ? "warning" : "ok"}">${issues.length ? `${issues.length} remaining issue(s)` : "All checks passed"}</strong><br>${repairs.length} targeted repair action(s) applied.`)}
    ${layer("Access model", `<strong>${bp.auth?.enabled ? "Authentication enabled" : "Public application"}</strong><br>${roles.length ? names(roles) : "No roles required"}.`)}
    ${layer("Assumptions", assumptions.length ? assumptions.map(escapeHtml).join("<br>") : "No additional assumptions recorded.")}
    ${layer("Warnings", bp.warnings?.length ? bp.warnings.map(escapeHtml).join("<br>") : "No blueprint warnings.")}
    ${layer("API contract", `<strong>${bp.api?.base_path || "/"}</strong><br>${bp.api?.endpoints?.length ?? 0} generated routes with interactive OpenAPI documentation.`)}
  </div>`;

  $("architecture-panel").innerHTML = `<div class="layer-grid">
    ${layer("UI pages", names(bp.ui?.pages))}
    ${layer("Database", names(bp.database?.tables))}
    ${layer("Roles", names(roles))}
    ${layer("API endpoints", (bp.api?.endpoints ?? []).map((ep) => `${escapeHtml(ep.method)} ${escapeHtml(ep.path)}`).join("<br>") || "None")}
    ${layer("Business rules", rules.map((rule) => escapeHtml(rule.name ?? rule.description)).join("<br>") || "None")}
    ${layer("Plans", names(bp.business_logic?.plans))}
  </div>`;

  const issueRows = issues.length
    ? issues.map((issue) => `<li><strong>${escapeHtml(issue.severity)}</strong> · ${escapeHtml(issue.code)} · ${escapeHtml(issue.message)}</li>`).join("")
    : `<li class="ok"><strong>PASS</strong> · No structural or cross-layer errors remain.</li>`;
  const repairRows = repairs.length
    ? repairs.map((action) => `<li><strong>${escapeHtml(action.tier)}</strong> · ${escapeHtml(action.description)}</li>`).join("")
    : `<li>No repair was required for this blueprint.</li>`;
  $("validation-panel").innerHTML = `<div class="layer-grid">
    <article class="layer"><h3 class="list-heading">Validation report</h3><ul class="compact-list">${issueRows}</ul></article>
    <article class="layer"><h3 class="list-heading">Repair history</h3><ul class="compact-list">${repairRows}</ul></article>
  </div>`;

  $("json-output").textContent = JSON.stringify(data, null, 2);
  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ── Compile ─────────────────────────────────────────────────── */
async function compile() {
  const prompt = promptInput.value.trim();
  if (!prompt) {
    promptInput.focus();
    return;
  }

  compileButton.disabled = true;
  results.hidden = true;
  $("clarification").hidden = true;
  $("error").hidden = true;
  setStatus(true, "Extracting intent", "Parsing features, roles, and requirements from your prompt.");
  animatePipelineSteps();

  try {
    const response = await fetch("/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed with status ${response.status}`);

    if (data.needs_clarification) {
      stopPipelineAnimation(false);
      $("clarification-text").textContent = data.clarifying_question;
      $("clarification").hidden = false;
      return;
    }
    stopPipelineAnimation(true);
    renderResult(data);
  } catch (error) {
    stopPipelineAnimation(false);
    $("error-text").textContent = error.message || "An unexpected error occurred.";
    $("error").hidden = false;
  } finally {
    setStatus(false);
    compileButton.disabled = false;
  }
}

/* ── Event listeners ─────────────────────────────────────────── */
document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    promptInput.value = examples[button.dataset.example];
    $("char-count").textContent = `${promptInput.value.length.toLocaleString()} / 10,000`;
    promptInput.focus();
  });
});

document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll('[role="tab"]').forEach((item) => item.setAttribute("aria-selected", "false"));
    document.querySelectorAll('[role="tabpanel"]').forEach((panel) => { panel.hidden = true; });
    tab.setAttribute("aria-selected", "true");
    $(tab.getAttribute("aria-controls")).hidden = false;
  });
});

promptInput.addEventListener("input", () => {
  $("char-count").textContent = `${promptInput.value.length.toLocaleString()} / 10,000`;
});
promptInput.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") compile();
});
compileButton.addEventListener("click", compile);

$("copy-json").addEventListener("click", async () => {
  if (!currentResult) return;
  await navigator.clipboard.writeText(JSON.stringify(currentResult, null, 2));
  $("copy-json").textContent = "Copied ✓";
  setTimeout(() => { $("copy-json").textContent = "Copy JSON"; }, 1400);
});

$("download-json").addEventListener("click", () => {
  if (!currentResult) return;
  const blob = new Blob([JSON.stringify(currentResult, null, 2)], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${currentResult.blueprint.app_name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-blueprint.json`;
  link.click();
  URL.revokeObjectURL(link.href);
});
