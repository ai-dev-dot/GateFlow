/* GateFlow — Chat streaming logic */

let currentConvId = null;
let isStreaming = false;

// --- Model selector ---
async function loadModels() {
  try {
    const res = await fetch('/api/gateway/models', { credentials: 'same-origin' });
    const models = await res.json();
    const select = document.getElementById('model-select');
    select.innerHTML = '';
    models.filter(m => m.is_active !== false).forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.alias;
      opt.textContent = m.alias;
      select.appendChild(opt);
    });
  } catch {}
}

// --- Conversation list ---
async function loadConversations() {
  try {
    const res = await fetch('/api/chat/conversations', { credentials: 'same-origin' });
    const convs = await res.json();
    const list = document.getElementById('conv-list');

    if (!convs.length) {
      list.innerHTML = '<div class="px-4 py-6 text-center text-gray-500 text-xs">暂无会话</div>';
      return;
    }

    // Group: today / yesterday / earlier
    const now = new Date();
    const today = []; const yesterday = []; const earlier = [];
    convs.forEach(c => {
      const d = new Date(c.updated_at || c.created_at);
      const diff = Math.floor((now - d) / 86400000);
      if (diff === 0) today.push(c);
      else if (diff === 1) yesterday.push(c);
      else earlier.push(c);
    });

    let html = '';
    const renderGroup = (label, items) => {
      if (!items.length) return;
      html += `<div class="px-4 py-1 text-xs text-gray-500 mt-2">${label}</div>`;
      items.forEach(c => {
        const active = c.id === currentConvId ? 'bg-gray-700' : 'hover:bg-gray-800';
        html += `<div class="conv-item group flex items-center justify-between px-4 py-2 cursor-pointer ${active}" data-id="${c.id}">
          <span class="truncate flex-1" onclick="selectConversation('${c.id}')">${c.title || '新会话'}</span>
          <button onclick="event.stopPropagation(); deleteConversation('${c.id}')" class="text-gray-500 hover:text-red-400 text-xs opacity-0 group-hover:opacity-100 ml-2">&times;</button>
        </div>`;
      });
    };
    renderGroup('今天', today);
    renderGroup('昨天', yesterday);
    renderGroup('更早', earlier);
    list.innerHTML = html;
  } catch {}
}

async function createConversation() {
  try {
    const res = await fetch('/api/chat/conversations', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '新会话' }),
    });
    const conv = await res.json();
    await loadConversations();
    selectConversation(conv.id);
  } catch {}
}

async function deleteConversation(id) {
  if (!confirm('确定删除此会话？')) return;
  try {
    await fetch(`/api/chat/conversations/${id}`, { method: 'DELETE', credentials: 'same-origin' });
    if (currentConvId === id) { currentConvId = null; clearMessages(); }
    loadConversations();
  } catch {}
}

async function selectConversation(id) {
  currentConvId = id;
  loadConversations();
  await loadMessages(id);
}

// --- Messages ---
function clearMessages() {
  document.getElementById('messages').innerHTML = '<div class="text-center text-gray-400 text-sm py-12">选择或创建一个会话开始对话</div>';
}

async function loadMessages(convId) {
  try {
    const res = await fetch(`/api/chat/conversations/${convId}/messages`, { credentials: 'same-origin' });
    const messages = await res.json();
    const container = document.getElementById('messages');

    if (!messages.length) {
      container.innerHTML = '<div class="text-center text-gray-400 text-sm py-12">发送第一条消息开始对话</div>';
      return;
    }

    container.innerHTML = messages.map(m => renderMessage(m)).join('');
    scrollToBottom();
  } catch {}
}

function renderMessage(m) {
  const isUser = m.role === 'user';
  const bubble = isUser ? 'msg-user' : 'msg-assistant';
  const content = escapeHtml(m.content || '').replace(/\n/g, '<br>');
  return `<div class="flex ${isUser ? 'justify-end' : 'justify-start'}">
    <div class="${bubble} prose-sm">${content}</div>
  </div>`;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function scrollToBottom() {
  const container = document.getElementById('messages');
  container.scrollTop = container.scrollHeight;
}

// --- Send message (streaming) ---
async function sendMessage() {
  if (isStreaming) return;

  const input = document.getElementById('chat-input');
  const text = input.value.trim();
  if (!text) return;
  if (!currentConvId) {
    await createConversation();
  }

  const model = document.getElementById('model-select').value;
  input.value = '';
  autoResize(input);

  // Optimistic: show user message
  const container = document.getElementById('messages');
  const placeholder = container.querySelector('.text-center');
  if (placeholder) placeholder.remove();

  container.innerHTML += `<div class="flex justify-end"><div class="msg-user prose-sm">${escapeHtml(text)}</div></div>`;
  container.innerHTML += `<div class="flex justify-start" id="ai-temp"><div class="msg-assistant prose-sm"><span class="cursor-blink"></span></div></div>`;
  scrollToBottom();

  isStreaming = true;
  document.getElementById('btn-send').disabled = true;

  try {
    const res = await fetch(`/api/chat/conversations/${currentConvId}/messages/stream`, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text, model: model || undefined }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || '发送失败');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let aiContent = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const data = line.slice(6);
        if (data === '[DONE]') continue;

        try {
          const parsed = JSON.parse(data);
          if (parsed.error) throw new Error(parsed.error.message || '流式错误');
          const delta = parsed.choices?.[0]?.delta?.content;
          if (delta) {
            aiContent += delta;
            const aiEl = document.getElementById('ai-temp');
            if (aiEl) aiEl.querySelector('.msg-assistant').innerHTML = escapeHtml(aiContent).replace(/\n/g, '<br>') + '<span class="cursor-blink"></span>';
            scrollToBottom();
          }
        } catch {}
      }
    }

    // Remove cursor, reload persisted messages
    const aiEl = document.getElementById('ai-temp');
    if (aiEl) aiEl.querySelector('.msg-assistant').innerHTML = escapeHtml(aiContent).replace(/\n/g, '<br>');
    await loadMessages(currentConvId);
    loadConversations();
  } catch (e) {
    const aiEl = document.getElementById('ai-temp');
    if (aiEl) aiEl.remove();
    showToast(e.message, 'error');
  } finally {
    isStreaming = false;
    document.getElementById('btn-send').disabled = false;
  }
}

// --- Auto-resize textarea ---
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

document.getElementById('chat-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

document.getElementById('chat-input').addEventListener('input', (e) => {
  autoResize(e.target);
});

// --- Init ---
loadModels();
loadConversations();
</script>
