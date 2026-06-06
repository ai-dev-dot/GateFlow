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
  const isError = type === 'error';
  Object.assign(toast.style, {
    position: 'fixed', top: '16px', right: '16px', zIndex: '9999',
    padding: '10px 18px', borderRadius: '8px', fontSize: '13px', fontWeight: '500',
    fontFamily: 'var(--font-sans)',
    background: isError ? 'rgba(248, 113, 113, 0.15)' : 'rgba(22, 24, 34, 0.95)',
    color: isError ? '#f87171' : '#e8eaf0',
    border: isError ? '1px solid rgba(248, 113, 113, 0.2)' : '1px solid rgba(255,255,255,0.1)',
    backdropFilter: 'blur(12px)',
    boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
    transition: 'opacity 0.3s',
  });
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 2500);
}

// ===== 表单错误处理 =====

// 字段名中英文映射
const FIELD_LABELS = {
  username: '用户名', password: '密码', email: '邮箱',
  name: '名称', provider: '供应商', key: 'API Key',
  model_alias: '模型别名', target_model: '目标模型', target_url: '目标 URL',
  priority: '优先级', default_temperature: 'Temperature', default_max_tokens: 'Max Tokens',
  remark: '备注', content: '内容', model: '模型',
  department_id: '部门', role_id: '角色', is_active: '状态',
  rpm_limit: 'RPM 限制', tpm_limit: 'TPM 限制',
  backup_dir: '备份目录', pg_dump_path: 'pg_dump 路径',
  permissions: '权限', rate_limit: '频率限制', expires_at: '过期时间',
  agent_type_id: '客户端类型', title: '标题',
};

// Pydantic 英文错误 → 中文翻译
function translateError(msg, label) {
  if (!msg) return `${label}无效`;
  if (msg === 'Field required') return `${label}不能为空`;
  if (msg === 'Input should be a valid string') return `请输入有效的${label}`;
  if (msg === 'Input should be a valid email address') return '请输入有效的邮箱地址';
  if (msg.includes('valid UUID')) return `${label}格式不正确`;
  if (msg.includes('ensure this value')) return `${label}值不合法`;
  if (msg.includes('at least')) return `${label}不满足最小长度要求`;
  if (msg.includes('at most')) return `${label}超出最大长度限制`;
  if (msg.includes('greater than')) return `${label}必须大于指定值`;
  if (msg.includes('less than')) return `${label}必须小于指定值`;
  if (msg.includes('Input should be a valid integer')) return `请输入有效的整数`;
  if (msg.includes('Input should be a valid number')) return `请输入有效的数字`;
  if (msg.includes('Input should be a valid boolean')) return `${label}格式不正确`;
  if (msg.includes('Field required')) return `${label}不能为空`;
  // 兜底：标签 + 原始信息
  return `${label}: ${msg}`;
}

// 清除表单上的所有错误
function clearFormErrors(formEl) {
  formEl.querySelectorAll('.field-error').forEach(el => el.remove());
  formEl.querySelectorAll('.border-red-500').forEach(el => el.classList.remove('border-red-500'));
  const formErr = formEl.querySelector('.form-level-error');
  if (formErr) formErr.remove();
}

// 在表单顶部显示无法定位到具体字段的错误
function showFormLevelError(formEl, msg) {
  let errDiv = formEl.querySelector('.form-level-error');
  if (!errDiv) {
    errDiv = document.createElement('div');
    errDiv.className = 'form-level-error gf-alert gf-alert-error mb-3';
    const firstChild = formEl.querySelector('input, select, textarea, .space-y-3, .grid');
    if (firstChild) {
      firstChild.parentNode.insertBefore(errDiv, firstChild);
    } else {
      formEl.prepend(errDiv);
    }
  }
  errDiv.textContent = msg;
}

// 主函数：处理表单错误（兼容 Pydantic 422 数组和字符串错误）
function showFormErrors(formEl, detail) {
  clearFormErrors(formEl);

  if (Array.isArray(detail)) {
    detail.forEach(err => {
      const loc = err.loc || [];
      // loc 通常是 ["body", "field_name"]，取最后一段
      const fieldName = loc[loc.length - 1];
      const label = FIELD_LABELS[fieldName] || fieldName || '未知字段';
      const msg = translateError(err.msg, label);

      // 尝试通过 data-field 或 name 属性定位字段
      const input = formEl.querySelector(`[data-field="${fieldName}"], [name="${fieldName}"]`);
      if (input) {
        input.classList.add('border-red-500');
        const errDiv = document.createElement('div');
        errDiv.className = 'field-error text-xs mt-1';
        errDiv.style.color = 'var(--danger)';
        errDiv.textContent = msg;
        // 插入到 input 的父容器末尾
        input.closest('div')?.appendChild(errDiv);
      } else {
        showFormLevelError(formEl, msg);
      }
    });
  } else if (typeof detail === 'string') {
    showFormLevelError(formEl, detail);
  } else {
    showFormLevelError(formEl, '操作失败');
  }
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

// Re-initialize Lucide icons after htmx content swaps
document.addEventListener('htmx:afterSwap', () => {
  if (typeof lucide !== 'undefined') lucide.createIcons();
});
