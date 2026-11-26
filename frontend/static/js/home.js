/* RETINOVA — home page: server status and the screening upload flow */

// ======================================================
// SERVER STATUS
// ======================================================

fetch('/api/health')
  .then(r => r.ok ? r.json() : Promise.reject())
  .then(() => { $('serverStatus').textContent = 'CONNECTED'; })
  .catch(() => {
    $('serverStatus').textContent = 'OFFLINE';
    $('serverStatus').classList.add('offline');
  });


// ======================================================
// SCREENING FLOW
// ======================================================

const screening = $('screening');
const input = $('fileInput');
const drop = $('dropzone');
const stepPreview = $('stepPreview');
const stepDone = $('stepDone');
const uploadBtn = $('uploadBtn');
const bar = $('bar');
const progressWrap = $('progressWrap');
const statusText = $('uploadStatus');
let current = null;

function showScreening() {
  screening.classList.remove('hidden');
  screening.scrollIntoView({ behavior: 'smooth' });
}

$('startBtn').addEventListener('click', showScreening);
$('navScreen').addEventListener('click', showScreening);
if (location.hash === '#screening') {
  showScreening();
}

function setUploadButton(text, disabled = false) {
  uploadBtn.disabled = disabled;
  uploadBtn.querySelector('span').textContent = text;
}

// Choose image
$('chooseBtn').addEventListener('click', () => input.click());
input.addEventListener('change', e => handle(e.target.files[0]));

// Drag and drop
['dragover', 'dragenter'].forEach(ev => drop.addEventListener(ev, e => {
  e.preventDefault();
  drop.classList.add('drag');
}));
['dragleave', 'drop'].forEach(ev => drop.addEventListener(ev, e => {
  e.preventDefault();
  drop.classList.remove('drag');
}));
drop.addEventListener('drop', e => handle(e.dataTransfer.files[0]));

// Show the selected image before uploading
function handle(file) {
  if (!file) {
    return;
  }
  if (!['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)) {
    alert('Accepted formats: JPG, JPEG, PNG');
    return;
  }

  const url = URL.createObjectURL(file);
  const img = new Image();

  img.onload = () => {
    current = { file, url };
    $('pvImg').src = url;
    $('mName').textContent = file.name;
    $('mSize').textContent = size(file.size);
    $('mW').textContent = img.naturalWidth + ' px';
    $('mH').textContent = img.naturalHeight + ' px';

    stepDone.classList.add('hidden');
    progressWrap.classList.add('hidden');
    bar.style.width = '0%';
    setUploadButton('Upload Image');
    stepPreview.classList.remove('hidden');
    stepPreview.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  img.onerror = () => {
    URL.revokeObjectURL(url);
    alert('The selected file could not be read as an image.');
  };

  img.src = url;
}

// Upload image
uploadBtn.addEventListener('click', () => {
  if (!current) {
    return;
  }

  setUploadButton('Uploading...', true);
  progressWrap.classList.remove('hidden');
  statusText.textContent = 'Sending image to RETINOVA server...';
  bar.style.width = '0%';

  // XMLHttpRequest (not fetch) so upload progress can be shown
  const request = new XMLHttpRequest();
  request.open('POST', '/api/upload');

  request.upload.addEventListener('progress', event => {
    if (event.lengthComputable) {
      const percent = Math.round(event.loaded / event.total * 100);
      bar.style.width = percent + '%';
      statusText.textContent = percent < 100
        ? 'Uploading... ' + percent + '%'
        : 'Analysing the retina...';
    }
  });

  request.onload = () => {
    let response = null;
    try {
      response = JSON.parse(request.responseText);
    } catch (error) {
      response = null;
    }

    if (request.status >= 200 && request.status < 300 && response) {
      bar.style.width = '100%';
      statusText.textContent = 'Analysis complete';
      showDone(response);
      return;
    }

    const message = request.status === 401
      ? 'Please log in as a patient before uploading an image.'
      : response?.detail || 'Upload failed. Please check that the RETINOVA server is running.';
    statusText.textContent = message;
    setUploadButton('Try Again');
    alert(message);
  };

  request.onerror = () => {
    statusText.textContent = 'Could not connect to the RETINOVA server.';
    setUploadButton('Try Again');
    alert('Could not connect to the RETINOVA server. Start the backend with start.bat.');
  };

  const formData = new FormData();
  formData.append('file', current.file);
  formData.append('eye', $('eyeSelect').value);
  request.send(formData);
});

// Show the screening result
function showDone(s) {
  $('dName').textContent = s.filename;
  $('dDim').textContent = s.width + ' × ' + s.height + ' px · ' + size(s.file_size);
  $('dTime').textContent = fmtDate(s.created_at);
  $('dQuality').textContent = s.quality;

  if (s.status === 'retake') {
    $('dTitle').textContent = 'Please Retake the Photo';
    $('dNote').textContent = s.quality_message +
      ' The image was not graded. Please capture a clearer fundus photo and upload it again.';
    $('dImg').src = current.url;
    setPill($('dGrade'), 'monitor', 'Not graded');
    ['dPrediction', 'dConfidence', 'dReferable', 'dAdvice']
      .forEach(id => { $(id).textContent = '—'; });
  } else {
    $('dTitle').textContent = 'Screening Complete';
    $('dNote').textContent =
      'The heatmap shows the regions that most influenced the AI grade. ' +
      'A doctor will review this result.';
    $('dImg').src = s.explanation_url || current.url;
    setPill($('dGrade'), s.urgency, gradeLabel(s.ai_grade));
    $('dPrediction').textContent = s.ai_prediction;
    $('dConfidence').textContent = s.confidence + '%';
    $('dReferable').textContent =
      (s.referable_dr ? 'Yes' : 'No') + ' (' + s.referable_probability + '%)';
    $('dAdvice').textContent = s.advice;
  }

  stepPreview.classList.add('hidden');
  stepDone.classList.remove('hidden');
  stepDone.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// Upload another image
$('againBtn').addEventListener('click', () => {
  if (current?.url) {
    URL.revokeObjectURL(current.url);
  }
  current = null;
  input.value = '';
  bar.style.width = '0%';
  progressWrap.classList.add('hidden');
  stepDone.classList.add('hidden');
  stepPreview.classList.add('hidden');
  setUploadButton('Upload Image');
  drop.scrollIntoView({ behavior: 'smooth', block: 'center' });
});
