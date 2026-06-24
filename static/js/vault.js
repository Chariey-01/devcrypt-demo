'use strict';

const vaultId   = window.VAULT_ID;
const timeLimit = window.VAULT_TIMER;
let   mcqDone   = window.MCQ_DONE;
const vaultDone = window.VAULT_COMPLETE;

// ── Timer ─────────────────────────────────────────────────────────────────
(function initTimer() {
  if (vaultDone) return;

  const display = document.getElementById('timer-display');
  const bar     = document.getElementById('timer-bar');
  if (!display || !bar) return;

  let startTime  = Date.now();
  let serverLeft = timeLimit;

  // Sync once from server
  fetch(`/api/timer/${vaultId}`)
    .then(r => r.json())
    .then(data => {
      serverLeft = data.remaining;
      startTime  = Date.now() - (timeLimit - serverLeft) * 1000;
    });

  function fmt(s) {
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  }

  function tick() {
    const elapsed  = (Date.now() - startTime) / 1000;
    const left     = Math.max(0, timeLimit - elapsed);
    const pct      = (left / timeLimit) * 100;

    display.textContent = fmt(left);
    bar.style.width     = pct + '%';

    if (left < 60) {
      bar.style.background = '#ff4d4f';
      display.classList.add('urgent');
    } else if (left < 120) {
      bar.style.background = '#ffd60a';
    }

    if (left > 0) {
      requestAnimationFrame(tick);
    } else {
      display.textContent = '00:00';
    }
  }

  requestAnimationFrame(tick);
})();


// ── MCQ submission ─────────────────────────────────────────────────────────
(function initMCQ() {
  const form = document.getElementById('mcq-form');
  if (!form || mcqDone) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('mcq-submit');
    btn.disabled = true;
    btn.textContent = 'Checking...';

    const fd = new FormData(form);
    const res = await fetch(`/vault/${vaultId}/mcq`, { method: 'POST', body: fd });
    const data = await res.json();

    if (data.error) { btn.disabled = false; btn.textContent = 'Submit answers'; return; }

    mcqDone = true;
    updateScore(data.score);

    // Colour options
    Object.entries(data.results).forEach(([qid, result]) => {
      const block = document.getElementById(`qblock-${qid}`);
      if (!block) return;
      block.querySelectorAll('.option-label').forEach(label => {
        const radio = label.querySelector('input[type=radio]');
        if (!radio) return;
        radio.disabled = true;
        if (radio.value === result.correct_answer) {
          label.classList.add('correct-opt');
        } else if (radio.checked && !result.correct) {
          label.classList.add('wrong-opt');
        }
      });
    });

    btn.remove();
    const resultEl = document.getElementById('mcq-result');
    resultEl.classList.remove('hidden');
    const correct = data.total_correct;
    const total   = Object.keys(data.results).length;
    if (correct === total) {
      resultEl.classList.add('success');
      resultEl.textContent = `All ${total} correct — +${total * 100} pts. Now code the fix.`;
    } else {
      resultEl.classList.add('partial');
      resultEl.textContent = `${correct}/${total} correct. Points adjusted. Now code the fix.`;
    }
  });
})();


// ── Code submission ────────────────────────────────────────────────────────
(function initCode() {
  const form = document.getElementById('code-form');
  if (!form) return;

  // Tab key inserts spaces
  const textarea = document.getElementById('code-input');
  textarea && textarea.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = textarea.selectionStart;
      const end   = textarea.selectionEnd;
      textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + 4;
    }
  });

  document.getElementById('clear-code')?.addEventListener('click', () => {
    if (textarea) textarea.value = '';
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn    = document.getElementById('code-submit');
    const result = document.getElementById('code-result');
    btn.disabled = true;
    btn.textContent = 'Evaluating...';

    const fd = new FormData(form);
    const res = await fetch(`/vault/${vaultId}/code`, { method: 'POST', body: fd });
    const data = await res.json();

    updateScore(data.score);
    result.classList.remove('hidden', 'pass', 'fail');

    if (data.passed) {
      result.classList.add('pass');
      result.innerHTML = `
        ✓ Vault unlocked — <strong>${data.revealed_word}</strong> revealed.
        Time used: ${data.time_used}s.
        ${data.next_vault
          ? `<a href="/vault/${data.next_vault}" class="inline-link" style="color:var(--accent)">Proceed to Vault 0${data.next_vault} →</a>`
          : `<a href="/board" class="inline-link" style="color:var(--accent)">View final board →</a>`
        }
      `;
      btn.remove();
      // Flip cipher tile
      const tile = document.getElementById(`tile-${vaultId}`);
      if (tile) {
        tile.classList.add('revealed');
        tile.innerHTML = `<span class="tile-plain">${data.revealed_word}</span>`;
      }
    } else {
      result.classList.add('fail');
      result.textContent = '✗ Not quite — check your keywords and try again. −30 pts.';
      btn.disabled = false;
      btn.textContent = 'Submit fix →';
    }
  });
})();
