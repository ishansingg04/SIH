const API_BASE = "http://localhost:8000/api/v1";

const SEED_USERS = {
  doctor: { email: "dr.sharma@medikiosk.in", password: "Doctor@12345", role: "doctor" },
  receptionist: { email: "reception@medikiosk.in", password: "Reception@12345", role: "receptionist" },
  admin: { email: "admin@medikiosk.in", password: "Admin@12345", role: "clinic_admin" },
  patient: { email: "asha.devi@medikiosk.in", password: "Patient@12345", role: "patient" },
};

let currentToken = null;
let currentSummaryId = null;
let currentSummaryPayload = null;

// DOM Elements
const userRoleSelect = document.getElementById("user-role");
const btnLogin = document.getElementById("btn-login");
const authStatus = document.getElementById("auth-status");
const visitIdInput = document.getElementById("visit-id");
const patientIdInput = document.getElementById("patient-id");
const btnLoadSeed = document.getElementById("btn-load-seed");
const btnGenerateSummary = document.getElementById("btn-generate-summary");
const chkForceRefresh = document.getElementById("chk-force-refresh");
const btnFetchHistory = document.getElementById("btn-fetch-history");
const evidenceContainer = document.getElementById("evidence-container");
const historyContainer = document.getElementById("history-container");
const rawJsonOutput = document.getElementById("raw-json-output");

// Summary Status Elements
const summaryBadge = document.getElementById("summary-badge");
const summaryVersion = document.getElementById("summary-version");
const summaryConfidence = document.getElementById("summary-confidence");
const summaryReviewer = document.getElementById("summary-reviewer");
const chiefComplaintText = document.getElementById("chief-complaint-text");
const patientReportedContent = document.getElementById("patient-reported-content");
const documentExtractedContent = document.getElementById("document-extracted-content");
const ayushAssessmentContent = document.getElementById("ayush-assessment-content");
const modelSuggestionsContent = document.getElementById("model-suggestions-content");

// Review Elements
const doctorNotesInput = document.getElementById("doctor-notes");
const btnApprove = document.getElementById("btn-approve");
const btnEdit = document.getElementById("btn-edit");
const btnReject = document.getElementById("btn-reject");

// Helper to make authenticated requests
async function apiRequest(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(currentToken ? { "Authorization": `Bearer ${currentToken}` } : {}),
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });
    const data = await response.json();
    rawJsonOutput.textContent = JSON.stringify(data, null, 2);
    return data;
  } catch (error) {
    console.error("API Request Error:", error);
    rawJsonOutput.textContent = JSON.stringify({ error: error.message }, null, 2);
    throw error;
  }
}

// 1. Authenticate user role
async function loginUser(roleKey = "doctor") {
  const credentials = SEED_USERS[roleKey];
  if (!credentials) return;

  try {
    const res = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: credentials.email, password: credentials.password }),
    });

    if (res.success && res.data.access_token) {
      currentToken = res.data.access_token;
      authStatus.textContent = `${credentials.role.toUpperCase()} Active`;
      authStatus.className = "badge badge-success";
    } else {
      authStatus.textContent = "Auth Failed";
      authStatus.className = "badge badge-danger";
    }
  } catch (err) {
    authStatus.textContent = "Auth Error (Offline)";
    authStatus.className = "badge badge-warning";
  }
}

// 2. Load Seed Data & Visit Info
async function loadSeedData() {
  evidenceContainer.innerHTML = `<div class="empty-state">Loading active visit context...</div>`;

  try {
    const res = await apiRequest("/summaries/demo/active-context");
    if (res.success && res.data && res.data.visit_id) {
      const data = res.data;
      visitIdInput.value = data.visit_id;
      patientIdInput.value = data.patient_id;

      let evidenceHtml = `
        <div class="evidence-item">
          <div class="evidence-meta">Patient: ${data.patient_name} | Token: ${data.token} | Pathway: ${data.intake_pathway}</div>
          <strong>Service Date:</strong> ${data.service_date || "Today"}
        </div>
      `;

      if (data.evidence && data.evidence.length > 0) {
        for (const ev of data.evidence) {
          evidenceHtml += `
            <div class="evidence-item">
              <div class="evidence-meta">${ev.kind} Input</div>
              <div>${ev.text || "Binary media captured"}</div>
            </div>
          `;
        }
      } else {
        evidenceHtml += `
          <div class="evidence-item">
            <div class="evidence-meta">Audio Transcript (Hindi)</div>
            <div>"मुझे दो दिन से हल्का बुखार और सूखी खांसी है, शाम को ज्यादा परेशानी होती है।"</div>
          </div>
          <div class="evidence-item">
            <div class="evidence-meta">Prescription OCR</div>
            <div>"Tab. Paracetamol 500mg SOS, Herbal Cough syrup 10ml TDS."</div>
          </div>
        `;
      }

      if (data.ayush_intake && Object.keys(data.ayush_intake).length > 0) {
        const ayush = data.ayush_intake;
        evidenceHtml += `
          <div class="evidence-item">
            <div class="evidence-meta">Dashavidha Pariksha Intake</div>
            <div><strong>Prakriti:</strong> ${ayush.prakriti?.primary_dosha || "VATA_PITTA"} | <strong>Agni:</strong> ${ayush.agni?.agni_type || "VISHAMA"} | <strong>Koshtha:</strong> ${ayush.koshtha?.koshtha_type || "KRURA"}</div>
          </div>
        `;
      }

      evidenceContainer.innerHTML = evidenceHtml;
    } else {
      evidenceContainer.innerHTML = `<div class="empty-state">No seeded visits found in DB. Run seed first.</div>`;
    }
  } catch (err) {
    evidenceContainer.innerHTML = `<div class="empty-state">Failed to fetch seed context: ${err.message}</div>`;
  }
}

// 3. Generate or Refresh Summary
async function generateSummary() {
  const visitId = visitIdInput.value.trim();
  if (!visitId) {
    alert("Please enter or auto-fill a Visit ID first.");
    return;
  }

  btnGenerateSummary.disabled = true;
  btnGenerateSummary.textContent = "⏳ Generating...";

  const forceRefresh = chkForceRefresh.checked;

  try {
    const res = await apiRequest(`/visits/${visitId}/summary`, {
      method: "POST",
      body: JSON.stringify({ force_refresh: forceRefresh }),
    });

    if (res.success && res.data) {
      renderSummary(res.data);
    } else {
      alert(`Error generating summary: ${res.error?.message || "Unknown error"}`);
    }
  } catch (err) {
    alert(`Failed to connect to API: ${err.message}`);
  } finally {
    btnGenerateSummary.disabled = false;
    btnGenerateSummary.textContent = "⚡ Generate Summary";
  }
}

// 4. Render Summary Payload
function renderSummary(data) {
  currentSummaryId = data.id;
  currentSummaryPayload = data.payload_json || {};

  summaryVersion.textContent = `v${data.version}`;
  summaryConfidence.textContent = `${Math.round((data.confidence || 0.9) * 100)}%`;
  summaryReviewer.textContent = data.reviewed_by ? data.reviewed_by.substring(0, 8) + "..." : "Unreviewed";

  // Status badge
  const status = data.review_status || "DRAFT";
  summaryBadge.textContent = status;
  if (status === "CONFIRMED") summaryBadge.className = "badge badge-success";
  else if (status === "EDITED") summaryBadge.className = "badge badge-warning";
  else if (status === "REJECTED") summaryBadge.className = "badge badge-danger";
  else summaryBadge.className = "badge badge-neutral";

  // Chief complaint
  const cc = currentSummaryPayload.chief_complaint?.value ||
             currentSummaryPayload.patient_reported?.chief_complaint ||
             "Fever and cough for 2 days";
  chiefComplaintText.textContent = cc;

  // 1. Patient Reported
  const pat = currentSummaryPayload.patient_reported || {};
  let patHtml = "";
  if (pat.symptoms && Array.isArray(pat.symptoms)) {
    patHtml += `<div class="fact-row"><span class="fact-key">Symptoms:</span><span class="fact-val">${pat.symptoms.join(", ")}</span></div>`;
  }
  if (pat.duration_days) {
    patHtml += `<div class="fact-row"><span class="fact-key">Duration:</span><span class="fact-val">${pat.duration_days} days</span></div>`;
  }
  patientReportedContent.innerHTML = patHtml || `<div class="empty-state">No patient facts parsed.</div>`;
  patientReportedContent.className = "section-content";

  // 2. Document Extracted
  const doc = currentSummaryPayload.document_extracted || {};
  let docHtml = "";
  if (doc.prior_prescriptions && Array.isArray(doc.prior_prescriptions)) {
    docHtml += `<div class="fact-row"><span class="fact-key">Prior Meds:</span><span class="fact-val">${doc.prior_prescriptions.join(", ")}</span></div>`;
  }
  if (doc.last_recorded_date) {
    docHtml += `<div class="fact-row"><span class="fact-key">Last Rx Date:</span><span class="fact-val">${doc.last_recorded_date}</span></div>`;
  }
  documentExtractedContent.innerHTML = docHtml || `<div class="empty-state">No document facts extracted.</div>`;
  documentExtractedContent.className = "section-content";

  // 3. AYUSH Dashavidha Pariksha
  const ayush = currentSummaryPayload.ayush_assessment || {};
  let ayushHtml = `<div class="ayush-card-grid">`;
  
  const ayushFields = [
    { key: "prakriti", label: "AYUSH - Prakriti", desc: ayush.prakriti?.primary_dosha || "Vata-Pitta" },
    { key: "vikriti", label: "AYUSH - Vikriti", desc: ayush.vikriti?.symptom_pattern || "Vata aggravation" },
    { key: "agni", label: "AYUSH - Agni", desc: ayush.agni?.appetite_level || "Vishama (Irregular)" },
    { key: "koshtha", label: "AYUSH - Koshtha", desc: ayush.koshtha?.bowel_regularity || "Krura (Constipated)" },
    { key: "sattva", label: "AYUSH - Sattva", desc: ayush.sattva?.sleep_quality || "Madhyama (Disturbed)" },
  ];

  for (const item of ayushFields) {
    ayushHtml += `
      <div class="ayush-chip">
        <div class="ayush-label">${item.label}</div>
        <div>${item.desc}</div>
      </div>
    `;
  }
  ayushHtml += `</div>`;
  ayushAssessmentContent.innerHTML = ayushHtml;
  ayushAssessmentContent.className = "section-content";

  // 4. Model Suggestions & Uncertainty
  const suggestions = currentSummaryPayload.model_suggestions || [];
  const uncertainties = currentSummaryPayload.uncertainty_labels || [];
  let modelHtml = "";

  for (const s of suggestions) {
    modelHtml += `
      <div class="suggestion-item">
        <strong>Suggestion:</strong> ${s.suggestion}
        <div style="font-size: 10px; color: #7e22ce; margin-top: 2px;">Category: ${s.category} (Confidence: ${Math.round((s.confidence || 0.85)*100)}%)</div>
      </div>
    `;
  }

  for (const u of uncertainties) {
    modelHtml += `
      <div class="uncertainty-item">
        <strong>Ambiguity / Note (${u.field}):</strong> ${u.reason}
      </div>
    `;
  }

  modelSuggestionsContent.innerHTML = modelHtml || `<div class="empty-state">No suggestions or uncertainties flagged.</div>`;
  modelSuggestionsContent.className = "section-content";

  // Enable review actions
  btnApprove.disabled = false;
  btnEdit.disabled = false;
  btnReject.disabled = false;
}

// 5. Doctor Review Actions
async function submitReview(decision) {
  if (!currentSummaryId) {
    alert("Please load or generate a summary first.");
    return;
  }

  let edits = null;
  if (decision === "EDIT") {
    const newChiefComplaint = prompt("Edit Chief Complaint:", chiefComplaintText.textContent);
    if (!newChiefComplaint) return;
    edits = {
      patient_reported: {
        ...currentSummaryPayload.patient_reported,
        chief_complaint: newChiefComplaint,
      },
      chief_complaint: {
        value: newChiefComplaint,
        source: "doctor_edited",
        confidence: 1.0,
      }
    };
  }

  const doctorNotes = doctorNotesInput.value.trim() || undefined;

  try {
    const res = await apiRequest(`/summaries/${currentSummaryId}/review`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        edits,
        doctor_notes: doctorNotes,
      }),
    });

    if (res.success) {
      alert(`Summary successfully reviewed with decision: ${decision}!`);
      renderSummary(res.data);
    } else {
      alert(`Review action failed: ${res.error?.message || "Forbidden or invalid role."}`);
    }
  } catch (err) {
    alert(`Review submission error: ${err.message}`);
  }
}

// 6. Fetch Longitudinal History
async function fetchPatientHistory() {
  const patientId = patientIdInput.value.trim();
  if (!patientId) {
    alert("Please enter a Patient ID.");
    return;
  }

  historyContainer.innerHTML = `<div class="empty-state">Loading longitudinal history...</div>`;

  try {
    const res = await apiRequest(`/patients/${patientId}/history`);
    if (res.success && res.data) {
      const data = res.data;
      let html = `<div style="margin-bottom: 8px;"><strong>Patient:</strong> ${data.patient_name} (${data.total_visits} encounters)</div>`;

      // Medications
      if (data.medications && data.medications.length > 0) {
        html += `<div style="margin-bottom: 6px;"><strong>Active / Prior Medications:</strong><br/>`;
        for (const med of data.medications) {
          html += `<span class="medication-tag">${med.name}</span>`;
        }
        html += `</div>`;
      }

      // Visits Timeline
      html += `<div style="margin-top: 8px;"><strong>Visits Timeline:</strong></div>`;
      for (const v of data.visits) {
        html += `
          <div class="history-visit-card">
            <div class="history-visit-header">
              <span>Date: ${v.service_date} (${v.token})</span>
              <span class="badge badge-neutral">${v.status}</span>
            </div>
            <div><strong>Complaint:</strong> ${v.chief_complaint || "Consultation"}</div>
            <div style="font-size: 11px; color: #64748b;">Pathway: ${v.intake_pathway} | Summary: ${v.summary_review_status || "Draft"}</div>
          </div>
        `;
      }

      historyContainer.innerHTML = html;
    } else {
      historyContainer.innerHTML = `<div class="empty-state">${res.error?.message || "Failed to load history."}</div>`;
    }
  } catch (err) {
    historyContainer.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
  }
}

// Event Listeners
btnLogin.addEventListener("click", () => loginUser(userRoleSelect.value));
userRoleSelect.addEventListener("change", () => loginUser(userRoleSelect.value));
btnLoadSeed.addEventListener("click", loadSeedData);
btnGenerateSummary.addEventListener("click", generateSummary);
btnFetchHistory.addEventListener("click", fetchPatientHistory);

btnApprove.addEventListener("click", () => submitReview("APPROVE"));
btnEdit.addEventListener("click", () => submitReview("EDIT"));
btnReject.addEventListener("click", () => submitReview("REJECT"));

// Initial setup
loginUser("doctor");
loadSeedData();
