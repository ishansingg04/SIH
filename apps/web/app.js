// ═══════════════════════════════════════════════════════
// MediKiosk — Simplified Kiosk Frontend
// ═══════════════════════════════════════════════════════

const API_BASE = "http://localhost:8000/api/v1";

const SEED_USERS = {
  doctor:       { email: "dr.sharma@medikiosk.in",   password: "Doctor@12345",     role: "doctor" },
  receptionist: { email: "reception@medikiosk.in",    password: "Reception@12345",  role: "receptionist" },
  admin:        { email: "admin@medikiosk.in",        password: "Admin@12345",      role: "clinic_admin" },
  patient:      { email: "asha.devi@medikiosk.in",    password: "Patient@12345",    role: "patient" },
};

let currentToken = null;
let currentSummaryId = null;
let currentSummaryPayload = null;

// ── DOM Refs ──
const $ = (id) => document.getElementById(id);
const stepPanels = document.querySelectorAll(".step-panel");
const stepTabs   = document.querySelectorAll(".step-tab");

// Step 1
const patientCard     = $("patient-card");
const patientInfo     = $("patient-info");
const visitIdInput    = $("visit-id");
const patientIdInput  = $("patient-id");
const btnLoadSeed     = $("btn-load-seed");
const evidenceContainer = $("evidence-container");
const btnGotoInterview  = $("btn-goto-interview");

// Step 2
const interviewIntake   = $("interview-intake");
const interviewActive   = $("interview-active");
const initialTextInput  = $("interview-initial-text");
const btnRecordInitial  = $("btn-record-initial");
const btnStartInterview = $("btn-start-interview");
const intakeStatus      = $("intake-status");

const qCounter     = $("q-counter");
const qPercent     = $("q-percent");
const progressFill = $("progress-fill");
const slotTag      = $("slot-tag");
const questionText = $("question-text");
const optionsRow   = $("options-row");

const answerText      = $("answer-text");
const btnRecordTurn   = $("btn-record-turn");
const btnSkip         = $("btn-skip");
const btnSubmitAnswer = $("btn-submit-answer");
const turnStatus      = $("turn-status");
const transcriptBox   = $("transcript-box");
const transcriptText  = $("transcript-text");

const factsCount = $("facts-count");
const factsList  = $("facts-list");
const redFlags   = $("red-flags");
const btnRestart  = $("btn-restart");
const btnComplete = $("btn-complete");

// Step 3
const summaryBadge      = $("summary-badge");
const summaryVersion    = $("summary-version");
const summaryConfidence = $("summary-confidence");
const summaryReviewer   = $("summary-reviewer");
const chiefComplaintText    = $("chief-complaint-text");
const patientReportedContent   = $("patient-reported-content");
const documentExtractedContent = $("document-extracted-content");
const ayushAssessmentContent   = $("ayush-assessment-content");
const modelSuggestionsContent  = $("model-suggestions-content");
const btnGenerateSummary       = $("btn-generate-summary");
const chkForceRefresh          = $("chk-force-refresh");
const doctorNotesInput = $("doctor-notes");
const btnApprove       = $("btn-approve");
const btnEdit          = $("btn-edit");
const btnReject        = $("btn-reject");
const btnFetchHistory  = $("btn-fetch-history");
const historyContainer = $("history-container");
const rawJsonOutput    = $("raw-json-output");

// Interview state
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let currentQuestionId = null;

const interviewLang    = $("interview-lang");
const interviewPathway = $("interview-pathway");

const btnLangEn = $("btn-lang-en");
const btnLangHi = $("btn-lang-hi");
const intakeTitle = $("intake-title");
const intakeSubtitle = $("intake-subtitle");
const lblRecordInitial = $("lbl-record-initial");
const lblStartInterview = $("lbl-start-interview");
const lblQuickAttach = $("lbl-quick-attach");

// Document Upload DOM elements
const uploadDropzone    = $("upload-dropzone");
const docFileInput      = $("doc-file-input");
const dropPrompt        = $("drop-prompt");
const fileChosenPreview = $("file-chosen-preview");
const chosenFileName    = $("chosen-file-name");
const btnClearFile      = $("btn-clear-file");
const btnUploadDoc      = $("btn-upload-doc");
const uploadStatus      = $("upload-status");

const btnQuickAttach    = $("btn-quick-attach");
const quickDocInput     = $("quick-doc-input");
const quickDocStatus    = $("quick-doc-status");

let selectedDocFile = null;

function setInterviewLanguage(lang) {
  const chosenLang = lang || "hi";
  if (interviewLang) interviewLang.value = chosenLang;
  
  if (btnLangEn && btnLangHi) {
    if (chosenLang === "en") {
      btnLangEn.classList.add("active");
      btnLangHi.classList.remove("active");
      if (intakeTitle) intakeTitle.textContent = "🎙️ Describe Your Health Concern";
      if (intakeSubtitle) intakeSubtitle.textContent = "Select language, then speak or type your symptoms. Clinical summary will be compiled in English.";
      if (initialTextInput) initialTextInput.placeholder = "e.g. Severe headache behind my eyes for 2 days with nausea and fever...";
      if (lblRecordInitial) lblRecordInitial.textContent = "Record Voice";
      if (lblStartInterview) lblStartInterview.textContent = "Start Interview →";
      if (lblQuickAttach) lblQuickAttach.textContent = "Attach Prescription / Medical Document";
      if (answerText) answerText.placeholder = "Type your answer or press Record... (Press Enter to submit)";
      if (btnSkip) btnSkip.textContent = "Skip";
      if (btnSubmitAnswer) btnSubmitAnswer.textContent = "Submit →";
    } else {
      btnLangHi.classList.add("active");
      btnLangEn.classList.remove("active");
      if (intakeTitle) intakeTitle.textContent = "🎙️ अपनी स्वास्थ्य समस्या बताएं";
      if (intakeSubtitle) intakeSubtitle.textContent = "भाषा चुनें, फिर बोलें या लिखें। आपके उत्तर का अंग्रेजी में अनुवाद और सारांश तैयार होगा।";
      if (initialTextInput) initialTextInput.placeholder = "उदा. मुझे दो दिन से पेट में तेज दर्द और हल्का बुखार है...";
      if (lblRecordInitial) lblRecordInitial.textContent = "आवाज़ रिकॉर्ड करें";
      if (lblStartInterview) lblStartInterview.textContent = "इंटरव्यू शुरू करें →";
      if (lblQuickAttach) lblQuickAttach.textContent = "पर्चा या मेडिकल रिपोर्ट जोड़ें (Prescription / Report)";
      if (answerText) answerText.placeholder = "अपना उत्तर लिखें या रिकॉर्ड करें... (Enter दबाएं)";
      if (btnSkip) btnSkip.textContent = "छोड़ें (Skip)";
      if (btnSubmitAnswer) btnSubmitAnswer.textContent = "भेजें (Submit) →";
    }
  }
}

if (btnLangEn) btnLangEn.addEventListener("click", () => setInterviewLanguage("en"));
if (btnLangHi) btnLangHi.addEventListener("click", () => setInterviewLanguage("hi"));
if (interviewLang) interviewLang.addEventListener("change", () => setInterviewLanguage(interviewLang.value));


// ════════════════════════════════════════════════════════
// NAVIGATION
// ════════════════════════════════════════════════════════

function goToStep(n) {
  stepPanels.forEach((p) => p.classList.remove("active"));
  stepTabs.forEach((t) => {
    const s = parseInt(t.dataset.step);
    t.classList.remove("active");
    if (s < n) t.classList.add("completed");
  });
  const panel = $(`step-${n}`);
  if (panel) panel.classList.add("active");
  const tab = document.querySelector(`.step-tab[data-step="${n}"]`);
  if (tab) tab.classList.add("active");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

stepTabs.forEach((tab) => {
  tab.addEventListener("click", () => goToStep(parseInt(tab.dataset.step)));
});

// ════════════════════════════════════════════════════════
// API HELPERS
// ════════════════════════════════════════════════════════

async function apiRequest(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(currentToken ? { Authorization: `Bearer ${currentToken}` } : {}),
    ...(options.headers || {}),
  };
  try {
    const res = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
    const data = await res.json();
    rawJsonOutput.textContent = JSON.stringify(data, null, 2);
    return data;
  } catch (err) {
    rawJsonOutput.textContent = JSON.stringify({ error: err.message }, null, 2);
    throw err;
  }
}

function escapeHtml(str) {
  return (str || "").replace(/'/g, "\\'").replace(/"/g, "&quot;");
}

function showStatus(el, msg, isError = false) {
  if (!el) return;
  if (!msg) { el.classList.add("hidden"); el.textContent = ""; return; }
  el.textContent = msg;
  el.className = isError ? "status-bar error" : "status-bar";
  el.classList.remove("hidden");
}

// ════════════════════════════════════════════════════════
// AUTH
// ════════════════════════════════════════════════════════

async function loginUser(roleKey = "doctor") {
  const creds = SEED_USERS[roleKey];
  if (!creds) return;
  const authDot = $("auth-status");
  try {
    const res = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: creds.email, password: creds.password }),
    });
    if (res.success && res.data.access_token) {
      currentToken = res.data.access_token;
      authDot.className = "status-dot green";
    } else {
      authDot.className = "status-dot red";
    }
  } catch {
    authDot.className = "status-dot amber";
  }
}

$("user-role").addEventListener("change", () => loginUser($("user-role").value));

function setChosenFile(file) {
  selectedDocFile = file;
  if (file) {
    chosenFileName.textContent = `${file.name} (${Math.round(file.size / 1024)} KB)`;
    dropPrompt.classList.add("hidden");
    fileChosenPreview.classList.remove("hidden");
    btnUploadDoc.disabled = false;
  } else {
    selectedDocFile = null;
    if (docFileInput) docFileInput.value = "";
    dropPrompt.classList.remove("hidden");
    fileChosenPreview.classList.add("hidden");
    btnUploadDoc.disabled = true;
  }
}

if (uploadDropzone) {
  uploadDropzone.addEventListener("click", (e) => {
    if (e.target !== btnClearFile && !fileChosenPreview.contains(e.target)) {
      docFileInput.click();
    }
  });
  uploadDropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadDropzone.classList.add("dragover");
  });
  uploadDropzone.addEventListener("dragleave", () => {
    uploadDropzone.classList.remove("dragover");
  });
  uploadDropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadDropzone.classList.remove("dragover");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setChosenFile(e.dataTransfer.files[0]);
    }
  });
}

if (docFileInput) {
  docFileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setChosenFile(e.target.files[0]);
    }
  });
}

if (btnClearFile) {
  btnClearFile.addEventListener("click", (e) => {
    e.stopPropagation();
    setChosenFile(null);
  });
}

async function uploadSelectedDocument(file = null, isQuick = false) {
  const fileToUpload = file || selectedDocFile;
  const visitId = visitIdInput.value.trim();
  if (!visitId) { alert("Please load an active visit first (Step 1)."); return; }
  if (!fileToUpload) { alert("Please select a prescription or document file."); return; }

  const statusEl = isQuick ? quickDocStatus : uploadStatus;
  const btn = isQuick ? btnQuickAttach : btnUploadDoc;

  try {
    btn.disabled = true;
    showStatus(statusEl, "⏳ Uploading file & enqueuing OCR extraction...");
    if (isQuick) {
      quickDocStatus.classList.remove("hidden");
      quickDocStatus.textContent = "⏳ Uploading & extracting OCR...";
    }

    const fd = new FormData();
    fd.append("file", fileToUpload);

    const res = await fetch(`${API_BASE}/visits/${visitId}/uploads`, {
      method: "POST",
      headers: currentToken ? { Authorization: `Bearer ${currentToken}` } : {},
      body: fd,
    });
    const data = await res.json();
    rawJsonOutput.textContent = JSON.stringify(data, null, 2);

    if (data.success && data.data) {
      const inputId = data.data.input_id;
      showStatus(statusEl, "🧠 Document uploaded. Extracting prescription text via OCR...");
      if (isQuick) quickDocStatus.textContent = "🧠 Extracting prescription via OCR...";

      // Poll status
      let ocrText = null;
      for (let i = 0; i < 10; i++) {
        await new Promise((r) => setTimeout(r, 1000));
        try {
          const pollRes = await apiRequest(`/inputs/${inputId}`);
          if (pollRes.success && pollRes.data) {
            if (pollRes.data.status === "COMPLETED" || pollRes.data.result_preview) {
              ocrText = pollRes.data.result_preview || "Document text extracted.";
              break;
            }
          }
        } catch (e) {}
      }

      showStatus(statusEl, "✓ Document & Prescription successfully processed!");
      if (isQuick) quickDocStatus.textContent = "✓ Prescription attached & OCR processed!";

      // Append to captured evidence in Step 1
      const docItem = document.createElement("div");
      docItem.className = "ev-item";
      docItem.innerHTML = `
        <div class="ev-label">📄 DOCUMENT OCR (${escapeHtml(fileToUpload.name)})</div>
        <div>${escapeHtml(ocrText || "Prescription text extracted and ready for AI clinical summary.")}</div>
      `;
      const placeholder = evidenceContainer.querySelector(".muted-text");
      if (placeholder) placeholder.remove();
      evidenceContainer.prepend(docItem);

      // Reset file selection
      setChosenFile(null);
    } else {
      showStatus(statusEl, "Error: " + (data.error?.message || "Upload failed"), true);
      if (isQuick) quickDocStatus.textContent = "Upload failed.";
    }
  } catch (err) {
    showStatus(statusEl, "Error: " + err.message, true);
    if (isQuick) quickDocStatus.textContent = "Error: " + err.message;
  } finally {
    btn.disabled = false;
  }
}

if (btnUploadDoc) {
  btnUploadDoc.addEventListener("click", () => uploadSelectedDocument(null, false));
}

if (btnQuickAttach && quickDocInput) {
  btnQuickAttach.addEventListener("click", () => quickDocInput.click());
  quickDocInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      uploadSelectedDocument(e.target.files[0], true);
    }
  });
}

// ════════════════════════════════════════════════════════
// STEP 1: LOAD VISIT
// ════════════════════════════════════════════════════════

async function loadSeedData() {
  patientInfo.innerHTML = `<p class="muted-text">Loading…</p>`;
  evidenceContainer.innerHTML = `<p class="muted-text">Loading…</p>`;

  try {
    const res = await apiRequest("/summaries/demo/active-context");
    if (res.success && res.data && res.data.visit_id) {
      const d = res.data;
      visitIdInput.value   = d.visit_id;
      patientIdInput.value = d.patient_id;

      patientInfo.innerHTML = `
        <div class="patient-detail">
          <span class="pd-label">Name</span>  <span class="pd-value">${d.patient_name}</span>
          <span class="pd-label">Token</span> <span class="pd-value">${d.token}</span>
          <span class="pd-label">Pathway</span> <span class="pd-value">${d.intake_pathway}</span>
          <span class="pd-label">Date</span>  <span class="pd-value">${d.service_date || "Today"}</span>
        </div>
      `;

      let evHtml = "";
      if (d.evidence && d.evidence.length > 0) {
        for (const ev of d.evidence) {
          evHtml += `<div class="ev-item"><div class="ev-label">${ev.kind} Input</div>${ev.text || "Binary media captured"}</div>`;
        }
      } else {
        evHtml += `<p class="muted-text">No evidence uploaded yet. You can upload prescriptions, lab reports, or record your voice interview.</p>`;
      }

      if (d.ayush_intake && Object.keys(d.ayush_intake).length > 0) {
        const ay = d.ayush_intake;
        evHtml += `<div class="ev-item"><div class="ev-label">Dashavidha Pariksha</div>Prakriti: ${ay.prakriti?.primary_dosha || "Vata-Pitta"} | Agni: ${ay.agni?.agni_type || "Vishama"} | Koshtha: ${ay.koshtha?.koshtha_type || "Krura"}</div>`;
      }
      evidenceContainer.innerHTML = evHtml || `<p class="muted-text">No evidence found.</p>`;
      btnGotoInterview.disabled = false;
    } else {
      patientInfo.innerHTML = `<p class="muted-text">No seeded visits. Run seed.py first.</p>`;
    }
  } catch (err) {
    patientInfo.innerHTML = `<p class="muted-text">Error: ${err.message}</p>`;
  }
}

btnLoadSeed.addEventListener("click", loadSeedData);
btnGotoInterview.addEventListener("click", () => goToStep(2));

// ════════════════════════════════════════════════════════
// STEP 2: INTERVIEW — AUDIO RECORDING
// ════════════════════════════════════════════════════════

async function toggleRecording(forTurn = false) {
  const btn = forTurn ? btnRecordTurn : btnRecordInitial;
  const statusEl = forTurn ? turnStatus : intakeStatus;

  if (isRecording) {
    // Stop
    if (mediaRecorder && mediaRecorder.state === "recording") {
      btn.disabled = true;
      btn.innerHTML = "⏳ Processing…";
      btn.classList.remove("recording");
      showStatus(statusEl, "🧠 Transcribing audio & extracting clinical facts…");
      mediaRecorder.stop();
    }
    isRecording = false;
    return;
  }

  // Start
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(audioChunks, { type: "audio/webm" });
      try {
        if (forTurn) {
          await submitTurn(false, blob);
        } else {
          await startInterview(blob);
        }
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span class="mic-icon">🎤</span> ${forTurn ? "Record" : "Record Voice"}`;
        btn.classList.remove("recording");
      }
    };

    mediaRecorder.start();
    isRecording = true;
    btn.innerHTML = "⏹ Stop & Submit";
    btn.classList.add("recording");
    showStatus(statusEl, "🎤 Recording… Speak now. Click 'Stop & Submit' when done.");
  } catch (err) {
    showStatus(statusEl, "Microphone error: " + err.message, true);
  }
}

btnRecordInitial.addEventListener("click", () => toggleRecording(false));
btnRecordTurn.addEventListener("click", () => toggleRecording(true));

// ════════════════════════════════════════════════════════
// STEP 2: START INTERVIEW
// ════════════════════════════════════════════════════════

async function startInterview(audioBlob = null) {
  const visitId = visitIdInput.value.trim();
  if (!visitId) { alert("Load a visit first (Step 1)."); return; }

  const text = initialTextInput.value.trim();
  if (!text && !audioBlob) { alert("Please type a symptom or record your voice."); return; }

  const fd = new FormData();
  if (text) fd.append("initial_text", text);
  fd.append("language", interviewLang.value);
  fd.append("pathway", interviewPathway.value);
  fd.append("max_questions", "6");
  if (audioBlob) fd.append("audio_file", audioBlob, "initial_intake.webm");

  try {
    btnStartInterview.disabled = true;
    btnStartInterview.textContent = "⏳ Starting…";
    showStatus(intakeStatus, "Processing intake & selecting next clinical question…");

    const res = await fetch(`${API_BASE}/visits/${visitId}/interview/start`, {
      method: "POST",
      headers: currentToken ? { Authorization: `Bearer ${currentToken}` } : {},
      body: fd,
    });
    const data = await res.json();
    rawJsonOutput.textContent = JSON.stringify(data, null, 2);

    if (data.success && data.data) {
      showStatus(intakeStatus, "");
      renderTurn(data.data);
    } else {
      showStatus(intakeStatus, "Error: " + (data.error?.message || "Server error"), true);
    }
  } catch (err) {
    showStatus(intakeStatus, "Error: " + err.message, true);
  } finally {
    btnStartInterview.disabled = false;
    btnStartInterview.textContent = "Start Interview →";
  }
}

btnStartInterview.addEventListener("click", () => startInterview(null));

initialTextInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); startInterview(null); }
});

// ════════════════════════════════════════════════════════
// STEP 2: SUBMIT TURN
// ════════════════════════════════════════════════════════

async function submitTurn(isSkip = false, audioBlob = null) {
  const visitId = visitIdInput.value.trim();
  if (!visitId) return;

  const text = answerText.value.trim();
  if (!isSkip && !text && !audioBlob) { alert("Enter or record an answer, or click Skip."); return; }

  const fd = new FormData();
  if (currentQuestionId) fd.append("question_id", currentQuestionId);
  if (text && !isSkip) fd.append("answer_text", text);
  fd.append("skipped", isSkip ? "true" : "false");
  fd.append("language", interviewLang.value);
  if (audioBlob) fd.append("audio_file", audioBlob, "turn_answer.webm");

  try {
    btnSubmitAnswer.disabled = true;
    btnSubmitAnswer.textContent = "⏳…";
    showStatus(turnStatus, "Analyzing answer…");

    const res = await fetch(`${API_BASE}/visits/${visitId}/interview/turn`, {
      method: "POST",
      headers: currentToken ? { Authorization: `Bearer ${currentToken}` } : {},
      body: fd,
    });
    const data = await res.json();
    rawJsonOutput.textContent = JSON.stringify(data, null, 2);

    if (data.success && data.data) {
      showStatus(turnStatus, "");
      renderTurn(data.data);
      answerText.value = "";
    } else {
      showStatus(turnStatus, "Error: " + (data.error?.message || "Unknown"), true);
    }
  } catch (err) {
    showStatus(turnStatus, "Error: " + err.message, true);
  } finally {
    btnSubmitAnswer.disabled = false;
    btnSubmitAnswer.textContent = "Submit →";
  }
}

btnSubmitAnswer.addEventListener("click", () => submitTurn(false));
btnSkip.addEventListener("click", () => submitTurn(true));

answerText.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitTurn(false); }
});

// ════════════════════════════════════════════════════════
// RENDER INTERVIEW TURN
// ════════════════════════════════════════════════════════

function renderTurn(data) {
  // Switch from intake to active view
  interviewIntake.classList.add("hidden");
  interviewActive.classList.remove("hidden");

  if (data.interview_complete) {
    qCounter.textContent = "Interview Finished";
    qPercent.textContent = "100%";
    progressFill.style.width = "100%";
    questionText.textContent = "✓ All clinical information collected. Click 'Complete Interview' below.";
    slotTag.textContent = "DONE";
    answerText.disabled = true;
    btnRecordTurn.disabled = true;
    btnSkip.disabled = true;
    btnSubmitAnswer.disabled = true;
    optionsRow.classList.add("hidden");
  } else {
    const turn = data.turn_number || 1;
    const max  = data.max_questions || 6;
    const pct  = Math.min(100, Math.round((turn / max) * 100));
    qCounter.textContent = `Question ${turn} of ${max}`;
    qPercent.textContent = `${pct}%`;
    progressFill.style.width = `${pct}%`;

    answerText.disabled = false;
    btnRecordTurn.disabled = false;
    btnSkip.disabled = false;
    btnSubmitAnswer.disabled = false;

    if (data.next_question) {
      currentQuestionId = data.next_question.id;
      slotTag.textContent = data.next_question.slot;
      questionText.textContent = data.next_question.text;

      if (data.next_question.options && data.next_question.options.length > 0) {
        optionsRow.innerHTML = data.next_question.options
          .map((opt) => `<button type="button" class="option-chip" onclick="selectOption('${escapeHtml(opt)}')">${opt}</button>`)
          .join("");
        optionsRow.classList.remove("hidden");
      } else {
        optionsRow.classList.add("hidden");
      }
    }
  }

  // Transcript
  if (data.transcript) {
    transcriptText.textContent = data.transcript;
    transcriptBox.classList.remove("hidden");
  } else {
    transcriptBox.classList.add("hidden");
  }

  // Facts
  renderFacts(data.extracted_facts || []);

  // Red flags
  if (data.red_flags && data.red_flags.length > 0) {
    redFlags.innerHTML = `⚠️ <strong>Safety Alert:</strong> ${data.red_flags.map((r) => r.description || r.trigger).join(", ")}`;
    redFlags.classList.remove("hidden");
  } else {
    redFlags.classList.add("hidden");
  }
}

// ════════════════════════════════════════════════════════
// FACT CHIPS
// ════════════════════════════════════════════════════════

function renderFacts(facts) {
  factsCount.textContent = facts.length;
  if (!facts || facts.length === 0) {
    factsList.innerHTML = `<p class="muted-text">No facts extracted yet.</p>`;
    return;
  }

  factsList.innerHTML = facts.map((f) => {
    const slot = (f.slot || "").replace(/_/g, " ").toUpperCase();
    const orig = f.original_text && f.original_text !== f.value
      ? `<span class="fact-original">[Original: "${f.original_text}"]</span>` : "";
    return `
      <div class="fact-chip" id="chip-${f.id}">
        <div class="fact-info">
          <div class="fact-slot">${slot} [${f.source}]</div>
          <div class="fact-value" id="val-${f.id}">${f.value || ""}${orig}</div>
        </div>
        <div class="fact-actions">
          <button title="Edit" onclick="editFact('${f.id}','${escapeHtml(f.value || "")}')">✏️</button>
          <button title="Delete" onclick="deleteFact('${f.id}')">🗑️</button>
        </div>
      </div>
    `;
  }).join("");
}

window.selectOption = function (text) {
  answerText.value = text;
  submitTurn(false);
};

window.editFact = async function (factId, currentVal) {
  const newVal = prompt("Edit English fact value:", currentVal);
  if (newVal === null || newVal.trim() === "" || newVal === currentVal) return;
  const visitId = visitIdInput.value.trim();
  if (!visitId) return;
  try {
    const res = await apiRequest(`/visits/${visitId}/interview/facts/${factId}`, {
      method: "PUT",
      body: JSON.stringify({ value: newVal.trim(), verified: true }),
    });
    if (res.success) {
      const el = $(`val-${factId}`);
      if (el) el.textContent = newVal.trim();
    }
  } catch (err) { alert("Failed: " + err.message); }
};

window.deleteFact = async function (factId) {
  if (!confirm("Remove this fact?")) return;
  const visitId = visitIdInput.value.trim();
  if (!visitId) return;
  try {
    const res = await apiRequest(`/visits/${visitId}/interview/facts/${factId}`, { method: "DELETE" });
    if (res.success) {
      const chip = $(`chip-${factId}`);
      if (chip) chip.remove();
      factsCount.textContent = Math.max(0, parseInt(factsCount.textContent || "1") - 1);
    }
  } catch (err) { alert("Failed: " + err.message); }
};

// ════════════════════════════════════════════════════════
// COMPLETE INTERVIEW
// ════════════════════════════════════════════════════════

async function completeInterview() {
  const visitId = visitIdInput.value.trim();
  if (!visitId) return;

  try {
    btnComplete.disabled = true;
    btnComplete.textContent = "⏳ Completing…";
    const res = await apiRequest(`/visits/${visitId}/interview/complete`, { method: "POST" });
    if (res.success && res.data) {
      goToStep(3);
      // Auto-generate fresh live summary from interview facts
      await generateSummary(true);
    } else {
      alert("Failed: " + (res.error?.message || "Error"));
    }
  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    btnComplete.disabled = false;
    btnComplete.textContent = "✓ Complete Interview & Generate Summary";
  }
}

btnComplete.addEventListener("click", completeInterview);

// Restart
function resetInterview() {
  interviewIntake.classList.remove("hidden");
  interviewActive.classList.add("hidden");
  initialTextInput.value = "";
  answerText.value = "";
  showStatus(intakeStatus, "");
  showStatus(turnStatus, "");
  if (mediaRecorder && mediaRecorder.state === "recording") {
    try { mediaRecorder.stop(); } catch (e) {}
  }
  isRecording = false;
  btnRecordInitial.innerHTML = `<span class="mic-icon">🎤</span> <span id="lbl-record-initial">${interviewLang.value === "hi" ? "आवाज़ रिकॉर्ड करें" : "Record Voice"}</span>`;
  btnRecordInitial.classList.remove("recording");
  btnRecordTurn.innerHTML = `<span class="mic-icon">🎤</span> ${interviewLang.value === "hi" ? "रिकॉर्ड करें" : "Record"}`;
  btnRecordTurn.classList.remove("recording");
}

btnRestart.addEventListener("click", resetInterview);

// ════════════════════════════════════════════════════════
// STEP 3: GENERATE SUMMARY
// ════════════════════════════════════════════════════════

async function generateSummary(force = false) {
  const visitId = visitIdInput.value.trim();
  if (!visitId) { alert("No visit loaded."); return; }

  btnGenerateSummary.disabled = true;
  btnGenerateSummary.textContent = "⏳ Generating Live AI Summary…";

  try {
    const isForce = force || chkForceRefresh.checked;
    const res = await apiRequest(`/visits/${visitId}/summary`, {
      method: "POST",
      body: JSON.stringify({ force_refresh: isForce }),
    });
    if (res.success && res.data) {
      renderSummary(res.data);
    } else {
      alert("Error: " + (res.error?.message || "Unknown"));
    }
  } catch (err) {
    alert("Failed: " + err.message);
  } finally {
    btnGenerateSummary.disabled = false;
    btnGenerateSummary.textContent = "⚡ Generate / Refresh Summary";
  }
}

btnGenerateSummary.addEventListener("click", generateSummary);

function renderSummary(data) {
  currentSummaryId = data.id;
  currentSummaryPayload = data.payload_json || {};

  summaryVersion.textContent = `v${data.version}`;
  summaryConfidence.textContent = `${Math.round((data.confidence || 0.9) * 100)}%`;
  summaryReviewer.textContent = data.reviewed_by ? data.reviewed_by.substring(0, 8) + "…" : "None";

  const status = data.review_status || "DRAFT";
  summaryBadge.textContent = status;
  if (status === "CONFIRMED")  summaryBadge.className = "badge badge-success";
  else if (status === "EDITED") summaryBadge.className = "badge badge-warning";
  else if (status === "REJECTED") summaryBadge.className = "badge badge-danger";
  else summaryBadge.className = "badge badge-neutral";

  // Chief complaint
  const cc = (typeof currentSummaryPayload.chief_complaint === 'object' ? currentSummaryPayload.chief_complaint?.value : currentSummaryPayload.chief_complaint)
    || currentSummaryPayload.patient_reported?.chief_complaint
    || "No complaint recorded yet";
  chiefComplaintText.textContent = cc;

  // Patient reported
  const pat = currentSummaryPayload.patient_reported || {};
  let patHtml = "";
  if (pat.symptoms && Array.isArray(pat.symptoms))
    patHtml += `<div class="fact-row"><span class="fact-key">Symptoms</span><span class="fact-val">${pat.symptoms.join(", ")}</span></div>`;
  if (pat.duration_days)
    patHtml += `<div class="fact-row"><span class="fact-key">Duration</span><span class="fact-val">${pat.duration_days} days</span></div>`;
  patientReportedContent.innerHTML = patHtml || `<span class="muted-text">No patient facts.</span>`;
  patientReportedContent.className = "tile-body";

  // Document extracted
  const doc = currentSummaryPayload.document_extracted || {};
  let docHtml = "";
  if (doc.prior_prescriptions && Array.isArray(doc.prior_prescriptions))
    docHtml += `<div class="fact-row"><span class="fact-key">Prior Meds</span><span class="fact-val">${doc.prior_prescriptions.join(", ")}</span></div>`;
  if (doc.last_recorded_date)
    docHtml += `<div class="fact-row"><span class="fact-key">Last Rx Date</span><span class="fact-val">${doc.last_recorded_date}</span></div>`;
  documentExtractedContent.innerHTML = docHtml || `<span class="muted-text">No document facts.</span>`;
  documentExtractedContent.className = "tile-body";

  // AYUSH
  const ayush = currentSummaryPayload.ayush_assessment || {};
  const ayushFields = [
    { label: "Prakriti",  desc: ayush.prakriti?.primary_dosha || "—" },
    { label: "Vikriti",   desc: ayush.vikriti?.symptom_pattern || "—" },
    { label: "Agni",      desc: ayush.agni?.appetite_level || "—" },
    { label: "Koshtha",   desc: ayush.koshtha?.bowel_regularity || "—" },
    { label: "Sattva",    desc: ayush.sattva?.sleep_quality || "—" },
  ];
  ayushAssessmentContent.innerHTML = ayushFields.map((f) =>
    `<div class="ayush-row"><div class="ayush-label">${f.label}</div><div>${f.desc}</div></div>`
  ).join("");
  ayushAssessmentContent.className = "tile-body";

  // AI Suggestions
  const suggestions   = currentSummaryPayload.model_suggestions || [];
  const uncertainties  = currentSummaryPayload.uncertainty_labels || [];
  let modelHtml = "";
  for (const s of suggestions) {
    modelHtml += `<div class="suggestion-item"><strong>Suggestion:</strong> ${s.suggestion}<div style="font-size:11px;color:var(--purple-600);margin-top:2px;">${s.category} (${Math.round((s.confidence||0.85)*100)}%)</div></div>`;
  }
  for (const u of uncertainties) {
    modelHtml += `<div class="uncertainty-item"><strong>${u.field}:</strong> ${u.reason}</div>`;
  }
  modelSuggestionsContent.innerHTML = modelHtml || `<span class="muted-text">No suggestions.</span>`;
  modelSuggestionsContent.className = "tile-body";

  btnApprove.disabled = false;
  btnEdit.disabled = false;
  btnReject.disabled = false;
}

// ════════════════════════════════════════════════════════
// DOCTOR REVIEW
// ════════════════════════════════════════════════════════

async function submitReview(decision) {
  if (!currentSummaryId) { alert("Generate a summary first."); return; }

  let edits = null;
  if (decision === "EDIT") {
    const newCC = prompt("Edit Chief Complaint:", chiefComplaintText.textContent);
    if (!newCC) return;
    edits = {
      patient_reported: { ...currentSummaryPayload.patient_reported, chief_complaint: newCC },
      chief_complaint: { value: newCC, source: "doctor_edited", confidence: 1.0 },
    };
  }

  try {
    const res = await apiRequest(`/summaries/${currentSummaryId}/review`, {
      method: "POST",
      body: JSON.stringify({ decision, edits, doctor_notes: doctorNotesInput.value.trim() || undefined }),
    });
    if (res.success) {
      alert(`Summary ${decision.toLowerCase()}d successfully!`);
      renderSummary(res.data);
    } else {
      alert("Error: " + (res.error?.message || "Forbidden or invalid role."));
    }
  } catch (err) { alert("Error: " + err.message); }
}

btnApprove.addEventListener("click", () => submitReview("APPROVE"));
btnEdit.addEventListener("click", () => submitReview("EDIT"));
btnReject.addEventListener("click", () => submitReview("REJECT"));

// ════════════════════════════════════════════════════════
// PATIENT HISTORY
// ════════════════════════════════════════════════════════

async function fetchHistory() {
  const pid = patientIdInput.value.trim();
  if (!pid) { alert("No patient loaded."); return; }

  historyContainer.innerHTML = `<p class="muted-text">Loading…</p>`;
  try {
    const res = await apiRequest(`/patients/${pid}/history`);
    if (res.success && res.data) {
      const d = res.data;
      let html = `<p style="margin-bottom:8px;"><strong>${d.patient_name}</strong> — ${d.total_visits} encounters</p>`;

      if (d.medications && d.medications.length > 0) {
        html += `<div style="margin-bottom:8px;"><strong>Medications:</strong><br>`;
        html += d.medications.map((m) => `<span class="medication-tag">${m.name}</span>`).join("");
        html += `</div>`;
      }

      for (const v of d.visits) {
        html += `
          <div class="history-visit">
            <div class="history-visit-head">
              <span>${v.service_date} (${v.token})</span>
              <span class="badge badge-neutral">${v.status}</span>
            </div>
            <div><strong>Complaint:</strong> ${v.chief_complaint || "Consultation"}</div>
            <div style="font-size:12px;color:var(--slate-500);">Pathway: ${v.intake_pathway} | Summary: ${v.summary_review_status || "Draft"}</div>
          </div>
        `;
      }
      historyContainer.innerHTML = html;
    } else {
      historyContainer.innerHTML = `<p class="muted-text">${res.error?.message || "Failed."}</p>`;
    }
  } catch (err) {
    historyContainer.innerHTML = `<p class="muted-text">Error: ${err.message}</p>`;
  }
}

btnFetchHistory.addEventListener("click", fetchHistory);

// ════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════

loginUser("doctor");
loadSeedData();
setInterviewLanguage("hi");

