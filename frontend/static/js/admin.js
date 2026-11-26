/* RETINOVA — admin portal: usage, users and model performance */

async function loadAdminPortal() {
  let data;
  try {
    data = await api('/api/admin/overview');
  } catch (error) {
    $('adminSummary').textContent = error.message;
    return;
  }

  const u = data.users;
  const sc = data.screenings;
  const sv = data.service;
  const model = data.model;
  const test = model.metrics?.test;

  setCount('statUsers', u.total);
  $('statUsersDetail').textContent =
    u.patient + ' patients · ' + u.doctor + ' doctors · ' + u.admin + ' admins';
  setCount('statScans', sc.total);
  setCount('statReferable', sc.referable);
  setCount('statReviewed', sc.reviewed);

  $('adminSummary').textContent = 'Model ' + model.file + ' running on ' + sv.ai_device.toUpperCase() +
    (sv.avg_inference_ms ? ' · average analysis time ' + sv.avg_inference_ms + ' ms' : '');

  $('serviceInference').textContent = 'Device: ' + sv.ai_device.toUpperCase() + ' · ' +
    (sv.avg_inference_ms ? sv.avg_inference_ms + ' ms average per image (grade + Grad-CAM)' : 'no images analysed yet');
  $('serviceStorage').textContent = 'Database ' + sv.database_mb + ' MB · uploads ' +
    sv.uploads_mb + ' MB · heatmaps ' + sv.explanations_mb + ' MB';
  setPill($('backlogPill'), sc.pending ? 'monitor' : 'clear',
    sc.pending ? sc.pending + ' awaiting review' : 'Up to date');
  $('serviceBacklog').textContent = sc.reviewed + ' signed off · ' + sc.retake +
    ' rejected for poor image quality';

  $('userBody').innerHTML = data.user_list.length
    ? data.user_list.map(x => '<tr>' +
        '<td>' + esc(x.full_name) + '</td>' +
        '<td>' + esc(x.email) + '</td>' +
        '<td class="capitalize">' + x.role + '</td>' +
        '<td>' + fmtDate(x.created_at, false) + '</td>' +
        '<td>' + (x.role === 'patient' ? x.screenings + ' screenings'
          : x.role === 'doctor' ? x.reviews + ' reviews' : '—') + '</td>' +
        '<td>' + fmtDate(x.last_active) + '</td>' +
        '</tr>').join('')
    : '<tr><td colspan="6">No users yet.</td></tr>';

  const pct = v => (v * 100).toFixed(1) + '%';
  const rows = [
    ['Model file', model.file + ' · ' + model.size_mb + ' MB'],
    ['Architecture', (model.metrics?.architecture || 'ResNet18') + ', 224×224 input'],
    ['Updated', model.updated],
    ['Referral threshold', 'P(grade 2–4) ≥ ' + model.referable_threshold]
  ];
  if (test) {
    rows.push(
      ['Test accuracy', pct(test.accuracy) + ' (' + test.images + ' images)'],
      ['Quadratic kappa', test.quadratic_kappa.toFixed(3)],
      ['Macro F1', test.macro_f1.toFixed(3)],
      ['Referable DR', 'sensitivity ' + pct(test.referable_sensitivity) +
        ' · specificity ' + pct(test.referable_specificity) +
        ' · AUC ' + test.referable_auc.toFixed(3)]
    );
  }
  $('modelMeta').innerHTML = rows.map(([k, v]) =>
    '<li><span>' + k + '</span><span>' + esc(v) + '</span></li>').join('');

  if (test) {
    $('gradeBody').innerHTML = test.per_class.map((c, g) => '<tr>' +
      '<td>' + gradeLabel(g) + '</td>' +
      '<td>' + c.precision.toFixed(2) + '</td>' +
      '<td>' + c.recall.toFixed(2) + '</td>' +
      '<td>' + c.f1.toFixed(2) + '</td>' +
      '<td>' + c.support + '</td>' +
      '<td>' + data.grade_counts[g] + '</td>' +
      '</tr>').join('');
    $('metricsNote').textContent = 'Held-out APTOS 2019 test set, evaluated ' +
      model.metrics.evaluated_at + '. Recall is lowest for Severe: those images are most often graded Moderate.';
  } else {
    $('metricsNote').textContent =
      'No evaluation found. Run: python train.py --evaluate models/' + model.file;
  }
}

loadAdminPortal();
