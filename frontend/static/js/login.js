/* RETINOVA — login / signup page */

const tabs = document.querySelectorAll('.tabs button');
let mode = 'login';

// Login / Signup tabs
tabs.forEach(button => {
  button.addEventListener('click', () => {
    mode = button.dataset.mode;
    tabs.forEach(x => x.classList.remove('on'));
    button.classList.add('on');
    $('signupOnly').classList.toggle('hidden', mode !== 'signup');
    $('authSubmit').querySelector('span').textContent =
      mode === 'signup' ? 'Create Account' : 'Sign In';
  });
});

$('authForm').addEventListener('submit', async event => {
  event.preventDefault();

  const email = $('email').value.trim();
  const password = $('pw').value;
  const submitButton = $('authSubmit');
  const label = submitButton.querySelector('span');
  const originalText = label.textContent;
  submitButton.disabled = true;
  label.textContent = mode === 'signup' ? 'Creating...' : 'Signing in...';

  const body = mode === 'signup'
    ? { full_name: $('fullname').value.trim(), email, password, role: $('role').value }
    : { email, password };

  try {
    const response = await fetch('/api/auth/' + mode, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || 'Request failed.');
    }
    location.href = '/' + data.user.role;
  } catch (error) {
    alert(error.message || 'Could not connect to the RETINOVA server.');
    submitButton.disabled = false;
    label.textContent = originalText;
  }
});
