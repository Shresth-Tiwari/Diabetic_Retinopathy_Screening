/* RETINOVA — doctor portal: urgency queue, case review, sign-off */

let selected = null;

async function loadQueue() {
  let data;
  try {
    data = await api('/api/doctor/queue');
  } catch (error) {
    $('queueSummary').textContent = error.message;
    return;
  }

  const st = data.stats;
  setCount('statAwaiting', st.awaiting);
  setCount('statUrgent', st.urgent);
  setCount('statToday', st.signed_today);
  setCount('statAgreement', st.agreement, 1, '%');
  $('queueSummary').textContent =
    st.awaiting + ' scan' + (st.awaiting === 1 ? '' : 's') + ' awaiting sign-off · ' +
    st.urgent + ' flagged urgent';

  $('pendingBody').innerHTML = data.pending.length
    ? data.pending.map(s => '<tr data-id="' + s.id + '">' +
        '<td>RTN-' + s.id + '</td>' +
        '<td>' + esc(s.patient_name || '—') + '</td>' +
        '<td>' + eyeLabel(s.eye) + '</td>' +
        '<td>' + gradeLabel(s.ai_grade) + '</td>' +
        '<td>' + s.confidence + '%</td>' +
        '<td>' + s.referable_probability + '%</td>' +
        '<td>' + pill(s.urgency) + '</td>' +
        '<td>' + fmtDate(s.created_at) + '</td>' +
        '</tr>').join('')
    : '<tr><td colspan="8">No scans awaiting review.</td></tr>';

  $('recentBody').innerHTML = data.recent.length
    ? data.recent.map(s => '<tr data-id="' + s.id + '">' +
        '<td>RTN-' + s.id + '</td>' +
        '<td>' + esc(s.patient_name || '—') + '</td>' +
        '<td>' + gradeLabel(s.ai_grade) + '</td>' +
        '<td>' + gradeLabel(s.final_grade) + '</td>' +
        '<td>' + (s.review.decision === 'confirmed'
          ? '<span class="pill ok">Confirmed</span>'
          : '<span class="pill warn">Overridden</span>') + '</td>' +
        '<td>Dr. ' + esc(s.review.doctor) + '</td>' +
        '<td>' + fmtDate(s.review.reviewed_at) + '</td>' +
        '</tr>').join('')
    : '<tr><td colspan="7">No reviews yet.</td></tr>';

  // Open the most urgent case automatically
  if (!selected && data.pending.length) {
    openCase(data.pending[0].id);
  }
  highlightSelected();
}

function highlightSelected() {
  document.querySelectorAll('tr[data-id]').forEach(tr =>
    tr.classList.toggle('selected', Number(tr.dataset.id) === selected?.id));
}

async function openCase(id) {
  const s = await api('/api/screenings/' + id);
  selected = s;
  highlightSelected();

  $('caseSection').classList.remove('hidden');
  $('caseImage').src = s.explanation_url || s.image_url;
  $('caseCaption').textContent =
    'Case RTN-' + s.id + ' · ' + eyeLabel(s.eye) + ' eye · uploaded ' + fmtDate(s.created_at) +
    ' · ' + s.width + '×' + s.height + ' px';
  setPill($('caseGrade'), s.urgency, gradeLabel(s.ai_grade));
  $('casePatient').textContent = s.patient_name || '—';
  $('caseConfidence').textContent = s.confidence + '%';
  $('caseReferable').textContent = s.referable_probability + '% (threshold ' +
    Math.round(s.referable_threshold * 100) + '%)';
  $('caseQuality').textContent = s.quality;
  $('caseAdvice').textContent = s.advice;
  $('caseProbabilities').innerHTML = s.probabilities.map((p, g) =>
    '<div><span>' + DR_CLASSES[g] + '</span><i><b style="width:' + (p * 100).toFixed(1) +
    '%"></b></i><span>' + (p * 100).toFixed(1) + '%</span></div>').join('');

  const reviewed = s.status === 'reviewed';
  $('finalGrade').value = reviewed ? s.final_grade : s.ai_grade;
  $('reviewComments').value = reviewed ? s.review.comments || '' : '';
  $('reviewDone').textContent = reviewed
    ? 'Signed by Dr. ' + s.review.doctor + ' on ' + fmtDate(s.review.reviewed_at) +
      '. Submitting again records a new review.'
    : '';
  updateSubmitLabel();
  $('caseSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function updateSubmitLabel() {
  const same = Number($('finalGrade').value) === selected?.ai_grade;
  $('reviewSubmit').querySelector('span').textContent =
    same ? 'Confirm & Sign Off' : 'Override & Sign Off';
}

$('finalGrade').addEventListener('change', updateSubmitLabel);
$('showHeatmap').addEventListener('click', () => {
  if (selected?.explanation_url) {
    $('caseImage').src = selected.explanation_url;
  }
});
$('showOriginal').addEventListener('click', () => {
  if (selected) {
    $('caseImage').src = selected.image_url;
  }
});

document.querySelectorAll('table.clickable tbody').forEach(tbody =>
  tbody.addEventListener('click', e => {
    const row = e.target.closest('tr[data-id]');
    if (row) {
      openCase(Number(row.dataset.id)).catch(error => alert(error.message));
    }
  }));

$('reviewForm').addEventListener('submit', async event => {
  event.preventDefault();
  if (!selected) {
    return;
  }
  const button = $('reviewSubmit');
  button.disabled = true;
  try {
    const s = await api('/api/screenings/' + selected.id + '/review', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        final_grade: Number($('finalGrade').value),
        comments: $('reviewComments').value
      })
    });
    $('reviewDone').textContent = 'Case RTN-' + s.id + ' signed off as ' +
      gradeLabel(s.final_grade) + '. ' + s.advice;
    selected = null;
    await loadQueue();
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
  }
});

loadQueue();
