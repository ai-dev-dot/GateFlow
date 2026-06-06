/* GateFlow — common JS (htmx config + utilities) */

// htmx configuration
htmx.config.defaultSwapStyle = 'innerHTML';
htmx.config.defaultSettleDelay = 50;

// Attach CSRF / auth headers to htmx requests (cookie-based session, no extra header needed).
// If we later add CSRF tokens, configure them here.

// Utility: copy text to clipboard
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('已复制到剪贴板');
  }).catch(() => {
    // Fallback for non-HTTPS
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    showToast('已复制到剪贴板');
  });
}

// Utility: toast notification
function showToast(message, type = 'success') {
  const toast = document.createElement('div');
  toast.className = 'fixed top-4 right-4 z-50 px-4 py-2 rounded shadow-lg text-sm font-medium transition-opacity duration-300 ' +
    (type === 'error' ? 'bg-red-600 text-white' : 'bg-gray-800 text-white');
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

// Utility: format bytes
function formatBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1024 ** 2) return (b / 1024).toFixed(1) + ' KB';
  if (b < 1024 ** 3) return (b / 1024 ** 2).toFixed(1) + ' MB';
  return (b / 1024 ** 3).toFixed(2) + ' GB';
}

// Utility: format duration
function formatDuration(ms) {
  if (ms < 1000) return ms + ' ms';
  return (ms / 1000).toFixed(1) + ' s';
}

// Utility: format datetime
function formatDateTime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// Highlight active sidebar link
document.addEventListener('DOMContentLoaded', () => {
  const path = window.location.pathname;
  document.querySelectorAll('.sidebar-link').forEach(link => {
    if (link.getAttribute('href') === path) {
      link.classList.add('active');
    }
  });
});
