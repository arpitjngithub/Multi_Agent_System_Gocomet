const fileInput = document.getElementById("fileInput");
const runButton = document.getElementById("runButton");
const sampleButton = document.getElementById("sampleButton");
const queryInput = document.getElementById("queryInput");
const queryButton = document.getElementById("queryButton");
const resultSummary = document.getElementById("resultSummary");
const extractionTable = document.getElementById("extractionTable");
const validationTable = document.getElementById("validationTable");
const reasoningBox = document.getElementById("reasoningBox");
const decisionCard = document.getElementById("decisionCard");
const queryOutput = document.getElementById("queryOutput");
const statusTrack = document.getElementById("statusTrack");

let currentDocumentId = null;

runButton.addEventListener("click", async () => {
  if (!fileInput.files.length) {
    resultSummary.textContent = "Choose a file first.";
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  setStage("queued");
  resultSummary.textContent = "Uploading document...";

  const response = await fetch("/api/pipeline/run", {
    method: "POST",
    body: formData,
  });
  const payload = await response.json();
  currentDocumentId = payload.document_id;
  pollRun();
});

sampleButton.addEventListener("click", async () => {
  const sample = await fetch("/sample_docs/clean_invoice.pdf");
  const blob = await sample.blob();
  const file = new File([blob], "clean_invoice.pdf", { type: "application/pdf" });
  const formData = new FormData();
  formData.append("file", file);
  setStage("queued");
  resultSummary.textContent = "Uploading sample document...";
  const response = await fetch("/api/pipeline/run", { method: "POST", body: formData });
  const payload = await response.json();
  currentDocumentId = payload.document_id;
  pollRun();
});

queryButton.addEventListener("click", async () => {
  const question = queryInput.value.trim();
  if (!question) {
    queryOutput.textContent = "Enter a question first.";
    return;
  }
  queryOutput.textContent = "Running query...";
  const response = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  const payload = await response.json();
  queryOutput.textContent =
    `Answer: ${payload.answer}\n\nSQL: ${payload.sql}\n\nRows:\n${JSON.stringify(payload.rows, null, 2)}`;
});

async function pollRun() {
  if (!currentDocumentId) return;
  const response = await fetch(`/api/pipeline/run/${currentDocumentId}`);
  const payload = await response.json();
  renderPayload(payload);
  if (payload.pipeline_status === "completed" || payload.pipeline_status === "failed") {
    return;
  }
  setTimeout(pollRun, 800);
}

function renderPayload(payload) {
  setStage(payload.current_stage);
  resultSummary.textContent = `${payload.filename} · status: ${payload.pipeline_status}`;

  if (payload.extraction_result) {
    extractionTable.innerHTML = buildExtractionTable(payload.extraction_result);
  }

  if (payload.validation_result) {
    validationTable.innerHTML = buildValidationTable(payload.validation_result);
  }

  if (payload.router_reasoning) {
    reasoningBox.textContent = payload.router_reasoning;
    decisionCard.classList.remove("hidden");
    decisionCard.innerHTML = `<span class="badge decision-${payload.router_decision}">${payload.router_decision}</span>`;
  }

  if (payload.error_message) {
    reasoningBox.textContent = payload.error_message;
  }
}

function buildExtractionTable(extraction) {
  const entries = Object.entries(extraction).filter(([key]) => !["source", "warnings", "raw_text_preview"].includes(key));
  const rows = entries.map(([field, data]) => {
    const confidence = Number(data.confidence || 0);
    const className = confidence >= 0.85 ? "confidence-green" : confidence >= 0.7 ? "confidence-yellow" : "confidence-red";
    return `
      <tr>
        <td>${field}</td>
        <td>${data.value ?? "-"}</td>
        <td class="${className}">${confidence.toFixed(2)}</td>
      </tr>
    `;
  }).join("");

  const warnings = extraction.warnings?.length
    ? `<p class="muted">Warnings: ${extraction.warnings.join(" | ")}</p>`
    : "";

  return `
    <table>
      <thead><tr><th>Field</th><th>Value</th><th>Confidence</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${warnings}
  `;
}

function buildValidationTable(validation) {
  const rows = Object.entries(validation.field_results).map(([field, data]) => `
    <tr>
      <td>${field}</td>
      <td>${data.status}</td>
      <td>${data.found ?? "-"}</td>
      <td>${data.expected ?? data.expected_prefix ?? "-"}</td>
    </tr>
  `).join("");

  return `
    <table>
      <thead><tr><th>Field</th><th>Status</th><th>Found</th><th>Expected</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="muted">${validation.summary}</p>
  `;
}

function setStage(stage) {
  [...statusTrack.querySelectorAll(".status-pill")].forEach((pill) => {
    pill.classList.remove("active", "done");
    const pillStage = pill.dataset.stage;
    const order = ["queued", "extracting", "validating", "routing", "done"];
    if (order.indexOf(pillStage) < order.indexOf(stage)) {
      pill.classList.add("done");
    } else if (pillStage === stage) {
      pill.classList.add("active");
    }
  });
}
