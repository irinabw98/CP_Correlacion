// Cambiar por la URL de Render cuando publiques el backend.
const API_BASE = "https://cp-correlacion.onrender.com";

let rows = [];
let columns = [];
let selectedGroup = new Set();
let selectedUnit = new Set();
let selectedDesc = new Set();
let autoDesc = new Set();

const $ = (id) => document.getElementById(id);

function splitLine(line, delimiter) {
  if (delimiter === "\t") return line.split("\t");
  const out = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      inQuotes = !inQuotes;
    } else if (ch === delimiter && !inQuotes) {
      out.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  out.push(current);
  return out.map(v => v.replace(/^"|"$/g, ""));
}

function detectDelimiter(text) {
  const first = text.split(/\r?\n/).find(l => l.trim());
  if (!first) return "\t";
  const tabs = (first.match(/\t/g) || []).length;
  const semis = (first.match(/;/g) || []).length;
  const commas = (first.match(/,/g) || []).length;
  if (tabs >= semis && tabs >= commas) return "\t";
  if (semis >= commas) return ";";
  return ",";
}

function parseTable(text) {
  const clean = text.trim();
  if (!clean) throw new Error("Pegá una tabla antes de detectar columnas.");
  const delimiter = detectDelimiter(clean);
  const lines = clean.split(/\r?\n/).filter(l => l.trim());
  const headers = splitLine(lines[0], delimiter).map(h => h.trim());
  if (headers.length < 2) throw new Error("No pude detectar encabezados válidos.");
  const parsed = lines.slice(1).map(line => {
    const values = splitLine(line, delimiter);
    const obj = {};
    headers.forEach((h, i) => { obj[h] = (values[i] ?? "").trim(); });
    return obj;
  });
  return { headers, parsed };
}

function fillSelect(select, values, preferred = null) {
  select.innerHTML = "";
  values.forEach(v => {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = v;
    select.appendChild(opt);
  });
  if (preferred && values.includes(preferred)) select.value = preferred;
}

function uniqueValues(col) {
  return [...new Set(rows.map(r => (r[col] ?? "").toString().trim()).filter(Boolean))].sort();
}

function guessValueColumn() {
  const exact = ["assessment_value", "value", "valor", "resultado", "result"];
  const lower = new Map(columns.map(c => [c.toLowerCase(), c]));
  for (const k of exact) if (lower.has(k)) return lower.get(k);
  return columns[1] || columns[0];
}

function guessSeColumn() {
  const lower = new Map(columns.map(c => [c.toLowerCase(), c]));
  return lower.get("se_name_mod") || lower.get("se_name") || columns[0];
}

function guessDefaults() {
  selectedGroup = new Set();
  selectedUnit = new Set();
  selectedDesc = new Set();

  const groupHints = ["trial", "trial_mod", "hibrido", "hybrid", "dosis", "dose", "treatment", "treatment_name"];
  const unitHints = ["plot", "plot_id", "rep", "replicate", "replicate_number", "block", "bloque", "unidad", "sample_id"];

  columns.forEach(c => {
    const lc = c.toLowerCase();
    if (groupHints.some(h => lc === h || lc.includes(h))) selectedGroup.add(c);
    if (unitHints.some(h => lc === h || lc.includes(h))) selectedUnit.add(c);
  });
}

function detectAutoDesc() {
  autoDesc = new Set();
  const seCol = $("seCol").value;
  const valueCol = $("valueCol").value;
  const group = [...selectedGroup];
  const reserved = new Set([seCol, valueCol, ...group, ...selectedUnit]);
  if (!group.length) return;

  const groups = new Map();

  rows.forEach(r => {
    const key = group.map(c => r[c] ?? "").join("|||~|||");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(r);
  });

  columns.forEach(col => {
    if (reserved.has(col)) return;

    let constantCount = 0;
    let tested = 0;

    for (const groupRows of groups.values()) {
      const vals = new Set(groupRows.map(r => (r[col] ?? "").toString().trim()).filter(Boolean));
      if (vals.size > 0) {
        tested++;
        if (vals.size === 1) constantCount++;
      }
    }

    if (tested > 0 && constantCount / tested >= 0.85) autoDesc.add(col);
  });

  autoDesc.forEach(c => selectedDesc.add(c));
}

function renderPreview() {
  const preview = $("dataPreview");
  const head = columns.map(c => `<th>${escapeHtml(c)}</th>`).join("");
  const body = rows.slice(0, 8).map(r => `<tr>${columns.map(c => `<td>${escapeHtml(r[c] ?? "")}</td>`).join("")}</tr>`).join("");
  preview.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#039;",'"':"&quot;"}[ch]));
}

function makeChip(col, type) {
  const chip = document.createElement("button");
  chip.type = "button";
  chip.className = "chip";
  chip.textContent = col;

  if (type === "group" && selectedGroup.has(col)) chip.classList.add("selected");
  if (type === "unit" && selectedUnit.has(col)) chip.classList.add("selected");

  if (type === "desc") {
    if (autoDesc.has(col)) chip.classList.add("auto");
    if (selectedDesc.has(col)) chip.classList.add("selected");
  }

  chip.addEventListener("click", () => {
    const target = type === "group" ? selectedGroup : type === "unit" ? selectedUnit : selectedDesc;
    if (target.has(col)) target.delete(col); else target.add(col);
    if (type === "group") detectAutoDesc();
    renderChips();
  });

  return chip;
}

function renderChips() {
  const seCol = $("seCol").value;
  const valueCol = $("valueCol").value;
  const reserved = new Set([seCol, valueCol]);

  const groupBox = $("groupChips");
  const unitBox = $("unitChips");
  const descBox = $("descChips");

  groupBox.innerHTML = "";
  unitBox.innerHTML = "";
  descBox.innerHTML = "";

  columns.forEach(col => {
    if (!reserved.has(col)) groupBox.appendChild(makeChip(col, "group"));
  });

  columns.forEach(col => {
    if (!reserved.has(col) && !selectedGroup.has(col)) unitBox.appendChild(makeChip(col, "unit"));
  });

  columns.forEach(col => {
    if (!reserved.has(col) && !selectedGroup.has(col) && !selectedUnit.has(col)) descBox.appendChild(makeChip(col, "desc"));
  });
}

function refreshVariables() {
  const seCol = $("seCol").value;
  const variables = uniqueValues(seCol);
  fillSelect($("varX"), variables, variables.find(v => v.toLowerCase().includes("fito")) || variables[0]);
  fillSelect($("varY"), variables, variables.find(v => v.toLowerCase().includes("rend")) || variables[1] || variables[0]);
}

async function checkApi() {
  try {
    const res = await fetch(`${API_BASE}/`, { cache: "no-store" });
    if (!res.ok) throw new Error("Backend no disponible");
    $("apiStatus").textContent = "Backend conectado";
    document.querySelector(".dot")?.classList.add("ok");
  } catch (_) {
    $("apiStatus").textContent = "Configurar URL de Render en app.js";
  }
}

function showMessage(text, type = "") {
  const box = $("messages");
  box.className = `messages ${type}`;
  box.textContent = text;
}

function toggleInfo() {
  $("infoPanel").classList.toggle("hidden");
}

$("parseBtn").addEventListener("click", () => {
  try {
    const parsed = parseTable($("dataInput").value);
    rows = parsed.parsed;
    columns = parsed.headers;

    const se = guessSeColumn();
    const value = guessValueColumn();

    fillSelect($("seCol"), columns, se);
    fillSelect($("valueCol"), columns, value);

    guessDefaults();
    refreshVariables();
    detectAutoDesc();
    renderPreview();
    renderChips();

    $("configPanel").classList.remove("hidden");
    $("columnPanel").classList.remove("hidden");
    $("runPanel").classList.remove("hidden");

    showMessage(`Detecté ${rows.length} filas y ${columns.length} columnas.`, "success");
  } catch (err) {
    showMessage(err.message, "error");
  }
});

$("clearBtn").addEventListener("click", () => {
  $("dataInput").value = "";
  rows = [];
  columns = [];
  $("dataPreview").innerHTML = "";
  $("configPanel").classList.add("hidden");
  $("columnPanel").classList.add("hidden");
  $("runPanel").classList.add("hidden");
  showMessage("");
});

$("infoBtn")?.addEventListener("click", toggleInfo);
$("infoNavBtn")?.addEventListener("click", toggleInfo);

$("dockTrigger")?.addEventListener("click", () => {
  $("sideDock")?.classList.toggle("open");
});

$("seCol").addEventListener("change", () => {
  refreshVariables();
  detectAutoDesc();
  renderChips();
});

$("valueCol").addEventListener("change", () => {
  detectAutoDesc();
  renderChips();
});

$("runBtn").addEventListener("click", async () => {
  if (!rows.length) return showMessage("Primero pegá y detectá una tabla.", "error");

  const payload = {
    rows,
    se_col: $("seCol").value,
    value_col: $("valueCol").value,
    variable_x: $("varX").value,
    variable_y: $("varY").value,
    group_cols: [...selectedGroup],
    unit_cols: [...selectedUnit],
    descriptive_cols: [...selectedDesc],
    method: $("method").value,
    aggregation: $("aggregation").value,
    conflict_mode: $("conflictMode").value,
    min_n: 3,
    analysis_name: $("analysisName").value || "correlacion"
  };

  if (payload.variable_x === payload.variable_y) {
    return showMessage("Elegí dos variables distintas para correlacionar.", "error");
  }

  $("progress").classList.remove("hidden");
  $("runBtn").disabled = true;
  showMessage("Procesando análisis y armando Excel...");

  try {
    const res = await fetch(`${API_BASE}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || "No se pudo generar el análisis.");
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = `CP_CORRELACION_${payload.analysis_name}.xlsx`;

    document.body.appendChild(a);
    a.click();
    a.remove();

    URL.revokeObjectURL(url);
    showMessage("Excel generado correctamente.", "success");
  } catch (err) {
    showMessage(err.message, "error");
  } finally {
    $("progress").classList.add("hidden");
    $("runBtn").disabled = false;
  }
});

checkApi();
