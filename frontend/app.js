// Global Application State
let currentDocId = null;
let currentDocBase64 = null;
let selectedAttack = 'PRINT_SCAN';

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initDocumentStudio();
  initVerificationCenter();
  initAttackSimulator();
  initTrustRegistry();
  initExperimentsLab();
});

// ============================================================================
// TAB NAVIGATION
// ============================================================================
function initTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(btn => {
    btn.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetId = `tab-${btn.dataset.tab}`;
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add('active');

      if (btn.dataset.tab === 'pki') loadTrustRegistry();
      if (btn.dataset.tab === 'experiments') loadExperimentPlots();
    });
  });
}

// ============================================================================
// TAB 1: DOCUMENT STUDIO
// ============================================================================
function initDocumentStudio() {
  const form = document.getElementById('doc-form');
  const btnGen = document.getElementById('btn-generate');
  const previewBox = document.getElementById('doc-preview-container');
  const actionsBar = document.getElementById('doc-actions-bar');
  const badgesBox = document.getElementById('gen-meta-badges');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    btnGen.disabled = true;
    btnGen.innerHTML = '<span class="btn-icon">⏳</span> Cryptographically Sealing...';

    const payload = {
      recipient_name: document.getElementById('inp-name').value,
      registration_number: document.getElementById('inp-reg').value,
      degree: document.getElementById('inp-degree').value,
      grade: document.getElementById('inp-grade').value,
      institution: document.getElementById('inp-inst').value,
      issuer_domain: document.getElementById('inp-issuer').value,
      template_id: document.getElementById('inp-template').value,
      script: document.getElementById('inp-script').value
    };

    try {
      const resp = await fetch('/api/documents/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();

      if (data.success) {
        currentDocId = data.document_id;
        currentDocBase64 = data.image_base64;

        previewBox.innerHTML = `<img src="${data.image_base64}" alt="Sealed Document" id="preview-sealed-img">`;
        actionsBar.style.display = 'flex';

        badgesBox.innerHTML = `
          <span class="badge badge-pulse">PSNR: ${data.watermark_metrics.psnr_db.toFixed(1)} dB</span>
          <span class="badge badge-outline">SSIM: ${data.watermark_metrics.ssim.toFixed(4)}</span>
        `;

        document.getElementById('btn-download-doc').href = data.image_base64;
        document.getElementById('btn-download-doc').download = `certificate_${data.document_id.slice(0, 8)}.png`;
      } else {
        alert('Generation error: ' + (data.detail || 'Unknown error'));
      }
    } catch (err) {
      alert('Network error generating document: ' + err.message);
    } finally {
      btnGen.disabled = false;
      btnGen.innerHTML = '<span class="btn-icon">🔏</span> Generate & Cryptographically Seal Document';
    }
  });

  // Transfer actions
  document.getElementById('btn-send-to-verify').addEventListener('click', () => {
    if (!currentDocBase64) return;
    setVerificationImage(currentDocBase64, `certificate_${currentDocId.slice(0, 8)}.png`);
    document.querySelector('.tab-btn[data-tab="verify"]').click();
  });

  document.getElementById('btn-send-to-attack').addEventListener('click', () => {
    if (!currentDocBase64) return;
    document.querySelector('.tab-btn[data-tab="attack"]').click();
  });
}

// ============================================================================
// TAB 2: VERIFICATION CENTER
// ============================================================================
let verifyImageBase64 = null;

function initVerificationCenter() {
  const fileInput = document.getElementById('file-input');
  const dropZone = document.getElementById('drop-zone');
  const btnRun = document.getElementById('btn-run-verify');

  fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (evt) => setVerificationImage(evt.target.result, file.name);
      reader.readAsDataURL(file);
    }
  });

  document.getElementById('btn-clear-verify').addEventListener('click', () => {
    verifyImageBase64 = null;
    document.getElementById('verify-preview-wrap').style.display = 'none';
    document.getElementById('drop-zone').style.display = 'block';
  });

  // Sample buttons
  document.getElementById('btn-load-genuine').addEventListener('click', () => {
    if (currentDocBase64) {
      setVerificationImage(currentDocBase64, 'genuine_original.png');
    } else {
      // Auto-generate quick certificate
      document.getElementById('btn-generate').click();
      setTimeout(() => {
        if (currentDocBase64) setVerificationImage(currentDocBase64, 'genuine_original.png');
      }, 1200);
    }
  });

  document.getElementById('btn-load-reprint').addEventListener('click', async () => {
    if (!currentDocBase64) {
      alert('Please generate a document in Studio first.');
      return;
    }
    const res = await fetch('/api/attack/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: currentDocBase64, attack_type: 'PRINT_SCAN' })
    });
    const data = await res.json();
    setVerificationImage(data.attacked_image_base64, 'reprinted_photocopy.png');
  });

  document.getElementById('btn-load-tamper').addEventListener('click', async () => {
    if (!currentDocBase64) {
      alert('Please generate a document in Studio first.');
      return;
    }
    const res = await fetch('/api/attack/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: currentDocBase64, attack_type: 'TAMPER' })
    });
    const data = await res.json();
    setVerificationImage(data.attacked_image_base64, 'tampered_document.png');
  });

  btnRun.addEventListener('click', async () => {
    if (!verifyImageBase64) {
      alert('Please upload or select a document image first.');
      return;
    }

    btnRun.disabled = true;
    btnRun.innerHTML = '<span class="btn-icon">⏳</span> Verifying 8 Security Layers...';

    try {
      const resp = await fetch('/api/documents/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: verifyImageBase64,
          doc_id_hint: currentDocId
        })
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        alert('Verification error: ' + (errData.detail || resp.statusText));
        return;
      }

      const result = await resp.json();
      if (!result || !result.layers) {
        alert('Server returned an unexpected verification response.');
        return;
      }

      renderVerificationResults(result);
    } catch (err) {
      alert('Verification network error: ' + err.message);
    } finally {
      btnRun.disabled = false;
      btnRun.innerHTML = '<span class="btn-icon">⚡</span> Execute Full 8-Stage Authentication';
    }
  });
}

function setVerificationImage(base64Str, filename) {
  verifyImageBase64 = base64Str;
  document.getElementById('verify-preview-img').src = base64Str;
  document.getElementById('verify-file-name').textContent = filename;
  document.getElementById('verify-preview-wrap').style.display = 'flex';
  document.getElementById('drop-zone').style.display = 'none';
}

function renderVerificationResults(res) {
  const verdictTag = document.getElementById('verdict-tag');
  const summaryBox = document.getElementById('verdict-summary-box');
  const latencyLabel = document.getElementById('latency-label');

  // Overall Verdict formatting
  verdictTag.className = 'verdict-tag';
  if (res.final_status === 'VERIFIED') {
    verdictTag.classList.add('verdict-verified');
    verdictTag.textContent = '✓ VERIFIED: AUTHENTIC';
  } else if (res.final_status === 'VERIFIED-WITH-WARNING') {
    verdictTag.classList.add('verdict-warning');
    verdictTag.textContent = '⚠ VERIFIED (DEGRADED)';
  } else if (res.final_status === 'SUSPICIOUS') {
    verdictTag.classList.add('verdict-suspicious');
    verdictTag.textContent = '⛔ SUSPICIOUS ANOMALY';
  } else {
    verdictTag.classList.add('verdict-invalid');
    verdictTag.textContent = '✖ INVALID / COUNTERFEIT';
  }

  summaryBox.textContent = res.summary;
  latencyLabel.textContent = `⚡ Total Pipeline Verification Latency: ${res.total_verification_time_ms} ms`;

  // Layer 1: QR Code
  const qr = res.layers.qr;
  updateLayerCard('qr', qr.status, qr.status === 'PASS' ? `Decoded payload for Doc ID ${res.document_id.slice(0, 8)}... (${qr.latency_ms}ms)` : qr.reason);

  // Layer 2: PKI Domain
  const pki = res.layers.pki;
  updateLayerCard('pki', pki.status, pki.status === 'PASS' ? `Issuer '${pki.domain}' is enrolled and ACTIVE in Trust Registry.` : (pki.reason || 'Untrusted domain'));

  // Layer 3: Signature
  const sig = res.layers.signature;
  updateLayerCard('sig', sig.status, sig.reason || `Ed25519 signature valid (${sig.latency_ms}ms)`);

  // Layer 4: Hash
  const hash = res.layers.hash_integrity;
  updateLayerCard('hash', hash.status, hash.reason);

  // Layer 5: Watermark
  const wm = res.layers.watermark;
  updateLayerCard('wm', wm.status, wm.status !== 'SKIPPED' ? `Normalized Correlation: ${wm.nc_score} (BER: ${wm.ber_percent}%)` : wm.reason);

  // Layer 6: Copy Detection A
  const copy = res.layers.copy_detection_A;
  updateLayerCard('copy', copy.status === 'PASS' ? 'PASS' : 'FLAG', `Copy Score: ${copy.copy_score} (Threshold: ${copy.threshold}). ${copy.verdict}`);

  // Layer 7: Edge AI C
  const ai = res.layers.edge_ai_C;
  updateLayerCard('ai', ai.status === 'PASS' ? 'PASS' : 'FLAG', `Predicted: ${ai.predicted_class} (${(ai.confidence*100).toFixed(1)}% conf). ${ai.note}`);

  // Layer 8: Typosquatting
  const typo = pki.typosquat_analysis;
  if (typo && typo.is_typosquat) {
    updateLayerCard('typo', 'FLAG', typo.warning);
  } else {
    updateLayerCard('typo', 'PASS', 'Domain is free of typosquatting or homoglyph spoofing.');
  }
}

function updateLayerCard(idSuffix, status, descText) {
  const badge = document.getElementById(`badge-${idSuffix}`);
  const desc = document.getElementById(`desc-${idSuffix}`);
  if (!badge || !desc) return;

  badge.className = 'layer-badge';
  if (status === 'PASS') {
    badge.classList.add('badge-pass');
    badge.textContent = 'PASS';
  } else if (status === 'WARN') {
    badge.classList.add('badge-warn');
    badge.textContent = 'WARN';
  } else if (status === 'FLAG') {
    badge.classList.add('badge-flag');
    badge.textContent = 'FLAG';
  } else if (status === 'SKIPPED') {
    badge.classList.add('badge-outline');
    badge.textContent = 'SKIPPED';
  } else {
    badge.classList.add('badge-fail');
    badge.textContent = 'FAIL';
  }

  desc.textContent = descText;
}

// ============================================================================
// TAB 3: ATTACK SIMULATOR
// ============================================================================
function initAttackSimulator() {
  const attackButtons = document.querySelectorAll('.btn-attack');
  attackButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      attackButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedAttack = btn.dataset.attack;
    });
  });

  document.getElementById('btn-execute-attack').addEventListener('click', async () => {
    if (!currentDocBase64) {
      alert('Please generate a document in Studio first.');
      return;
    }

    const btn = document.getElementById('btn-execute-attack');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-icon">⏳</span> Simulating Distortion & Verifying...';

    try {
      const resp = await fetch('/api/attack/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_base64: currentDocBase64,
          document_id: currentDocId,
          attack_type: selectedAttack
        })
      });
      const data = await resp.json();

      const previewBox = document.getElementById('attack-preview-container');
      previewBox.innerHTML = `<img src="${data.attacked_image_base64}" alt="Distorted Document">`;

      const tag = document.getElementById('attack-verdict-tag');
      tag.className = 'verdict-tag';
      const status = data.verification_result.final_status;
      if (status === 'VERIFIED') tag.classList.add('verdict-verified');
      else if (status === 'VERIFIED-WITH-WARNING') tag.classList.add('verdict-warning');
      else if (status === 'SUSPICIOUS') tag.classList.add('verdict-suspicious');
      else tag.classList.add('verdict-invalid');
      tag.textContent = status;

      const diagBox = document.getElementById('attack-diagnostics');
      diagBox.style.display = 'block';
      diagBox.innerHTML = `
        <strong>Distortion Impact Analysis (${data.attack_type}):</strong><br>
        • Verdict: <strong>${status}</strong> (${data.verification_result.total_verification_time_ms} ms)<br>
        • ${data.verification_result.summary}<br>
        • Watermark NC: <strong>${data.verification_result.layers.watermark.nc_score || 'N/A'}</strong><br>
        • Component A Copy Score: <strong>${data.verification_result.layers.copy_detection_A.copy_score}</strong><br>
        • Edge AI Diagnosis: <strong>${data.verification_result.layers.edge_ai_C.predicted_class}</strong>
      `;
    } catch (err) {
      alert('Attack simulation failed: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-icon">⚡</span> Apply Attack & Run Instant Verification';
    }
  });
}

// ============================================================================
// TAB 4: WEB-PKI TRUST REGISTRY
// ============================================================================
function initTrustRegistry() {
  document.getElementById('btn-refresh-pki').addEventListener('click', loadTrustRegistry);

  document.getElementById('btn-check-domain').addEventListener('click', async () => {
    const domain = document.getElementById('inp-check-domain').value.trim();
    if (!domain) return;

    const resp = await fetch('/api/trust-registry/check-domain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain: domain })
    });
    const data = await resp.json();

    const box = document.getElementById('domain-audit-box');
    box.style.display = 'block';
    document.getElementById('audit-sim-val').textContent = `${(data.similarity * 100).toFixed(1)}%`;
    document.getElementById('audit-matched-val').textContent = data.matched_domain || 'N/A';

    const flag = document.getElementById('audit-flag-val');
    const note = document.getElementById('audit-note');
    if (data.is_trusted) {
      flag.className = 'badge badge-pulse';
      flag.textContent = 'EXACT TRUSTED MATCH';
      note.textContent = 'This domain matches an officially enrolled institutional authority.';
    } else if (data.is_typosquat) {
      flag.className = 'badge badge-fail';
      flag.textContent = 'TYPOSQUATTING / SPOOFING DETECTED';
      note.textContent = data.warning;
    } else {
      flag.className = 'badge badge-outline';
      flag.textContent = 'UNRELATED UNENROLLED DOMAIN';
      note.textContent = 'Domain is distinct from trusted authorities but not enrolled in PKI.';
    }
  });
}

async function loadTrustRegistry() {
  try {
    const resp = await fetch('/api/trust-registry');
    const issuers = await resp.json();
    const tbody = document.getElementById('pki-table-body');
    tbody.innerHTML = '';

    issuers.forEach(iss => {
      const tr = document.createElement('tr');
      const isRevoked = iss.status === 'REVOKED';
      tr.innerHTML = `
        <td><strong>${iss.issuer_id}</strong></td>
        <td><code>${iss.domain}</code></td>
        <td><code>${iss.key_id}</code></td>
        <td><span class="badge ${isRevoked ? 'badge-fail' : 'badge-pulse'}">${iss.status}</span></td>
        <td>
          ${isRevoked ? '<span class="text-muted">Revoked</span>' : `<button class="btn btn-small btn-warning" onclick="revokeKey('${iss.key_id}')">Revoke Key</button>`}
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load trust registry', err);
  }
}

async function revokeKey(keyId) {
  if (!confirm(`Are you sure you want to revoke key '${keyId}'? Verifications will fail instantly.`)) return;

  const resp = await fetch('/api/trust-registry/revoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key_id: keyId })
  });
  const data = await resp.json();

  const latencyBox = document.getElementById('revocation-latency-box');
  latencyBox.style.display = 'block';
  document.getElementById('revocation-latency-text').innerHTML = `
    Key <code>${keyId}</code> revoked in <strong>${data.revocation_latency_ms} ms</strong>.
    All subsequent verifications for this key will be rejected immediately (Gap 6).
  `;
  loadTrustRegistry();
}

// ============================================================================
// TAB 5: EXPERIMENTS & RESEARCH LAB
// ============================================================================
function initExperimentsLab() {
  document.getElementById('btn-run-ablation').addEventListener('click', async () => {
    const btn = document.getElementById('btn-run-ablation');
    btn.disabled = true;
    btn.textContent = 'Running 5-Stage Ablation Matrix...';
    try {
      await fetch('/api/experiments/ablation?sample_count=4', { method: 'POST' });
      await loadExperimentPlots();
      await loadVerificationLogs();
      alert('5-Stage Ablation Study completed successfully! Plots updated.');
    } catch (err) {
      alert('Ablation error: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run 5-Stage Ablation Benchmark';
    }
  });

  document.getElementById('btn-run-cross').addEventListener('click', async () => {
    const btn = document.getElementById('btn-run-cross');
    btn.disabled = true;
    btn.textContent = 'Running Multi-Condition Matrix...';
    try {
      const resp = await fetch('/api/experiments/cross-condition', { method: 'POST' });
      const data = await resp.json();
      await loadVerificationLogs();
      alert(`Cross-condition evaluation complete across ${data.evaluated_conditions} combinations! Avg latency: ${data.avg_latency_ms}ms.`);
    } catch (err) {
      alert('Matrix error: ' + err.message);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run Multi-Condition Matrix';
    }
  });
}

async function loadExperimentPlots() {
  try {
    const resp = await fetch('/api/results/plots');
    const data = await resp.json();

    document.getElementById('ablation-chart-wrap').innerHTML = `<img src="${data.ablation_chart_base64}" alt="Ablation Chart">`;
    document.getElementById('roc-chart-wrap').innerHTML = `<img src="${data.roc_plot_base64}" alt="ROC Plot">`;
    loadVerificationLogs();
  } catch (err) {
    console.error('Failed to load plots', err);
  }
}

async function loadVerificationLogs() {
  try {
    const resp = await fetch('/api/logs?limit=10');
    const logs = await resp.json();
    const tbody = document.getElementById('logs-table-body');
    tbody.innerHTML = '';

    logs.forEach(l => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><small>${l.timestamp.split('T')[1].slice(0, 8)}</small></td>
        <td><code>${l.document_id ? l.document_id.slice(0, 8) : 'N/A'}</code></td>
        <td>${l.qr_status}</td>
        <td>${l.signature_status}</td>
        <td>${l.watermark_score.toFixed(3)}</td>
        <td>${l.copy_score.toFixed(3)}</td>
        <td>${l.ai_status}</td>
        <td><span class="badge ${l.final_status === 'VERIFIED' ? 'badge-pulse' : 'badge-fail'}">${l.final_status}</span></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error('Failed to load logs', err);
  }
}
