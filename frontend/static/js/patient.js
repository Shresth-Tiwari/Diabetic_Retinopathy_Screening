/* RETINOVA — patient portal: latest result and screening history */

async function loadPatientPortal() {
  let data;
  try {
    data = await api('/api/patient/screenings');
  } catch (error) {
    $('patientSummary').textContent = error.message;
    return;
  }

  // History table
  if (data.history.length) {
    $('historyBody').innerHTML = data.history.map(s => '<tr>' +
      '<td>' + fmtDate(s.created_at) + '</td>' +
      '<td>' + eyeLabel(s.eye) + '</td>' +
      '<td>' + (s.grade !== undefined ? gradeLabel(s.grade) : 'Not graded') + '</td>' +
      '<td>' + (s.review ? 'Dr. ' + esc(s.review.doctor) : s.status === 'retake' ? '—' : 'AI screening') + '</td>' +
      '<td>' + statusPill(s) + '</td>' +
      '</tr>').join('');
  }

  const s = data.latest;
  if (!s) {
    return;
  }

  setPill($('patientGrade'), s.urgency, gradeLabel(s.grade));
  $('patientPrediction').textContent = s.ai_prediction;
  $('patientConfidence').textContent = s.confidence + '%';
  $('patientReferable').textContent = s.referable_dr ? 'Yes' : 'No';
  $('patientReferableProbability').textContent = s.referable_probability + '%';
  $('patientQuality').textContent = s.quality;
  $('patientAdvice').textContent = s.advice;
  $('patientNext').textContent = s.next_screening
    ? fmtDate(s.next_screening, false)
    : 'After your specialist visit';

  if (s.review) {
    $('patientReview').textContent = 'Dr. ' + s.review.doctor + ' · ' + fmtDate(s.review.reviewed_at, false);
    $('patientSummary').textContent =
      'Dr. ' + s.review.doctor + ' reviewed your screening from ' + fmtDate(s.created_at, false) +
      ' and graded it ' + s.grade_name + '. ' + s.advice +
      (s.review.comments ? ' Doctor\'s note: "' + s.review.comments + '"' : '');
  } else {
    $('patientReview').textContent = 'Pending';
    $('patientSummary').textContent =
      'The AI screening from ' + fmtDate(s.created_at, false) + ' classified this image as ' +
      s.ai_prediction + (s.referable_dr ? ' and marked it as referable. ' : '. ') + s.advice +
      ' A doctor will review the result.';
  }

  if (s.explanation_url) {
    $('patientExplanation').src = s.explanation_url;
    $('patientExplanation').alt = 'Grad-CAM explanation of your latest screening';
    $('patientExplanationNote').textContent =
      'The bright regions show the areas of your retina that most influenced the AI grade.';
  }
}

loadPatientPortal();
