import client from './client';
import type { Conversation, Message } from '../types';

/** 会话列表（后端返回数组） */
export async function listConversations(): Promise<Conversation[]> {
  const res = await client.get('/chat/conversations');
  return res.data;
}

/** 创建会话 */
export async function createConversation(data: {
  title?: string;
  model_id?: string;
}): Promise<Conversation> {
  const res = await client.post('/chat/conversations', data);
  return res.data;
}

/** 获取消息列表（后端返回数组） */
export async function getMessages(
  conversationId: string,
): Promise<Message[]> {
  const res = await client.get(`/chat/conversations/${conversationId}/messages`);
  return res.data;
}

/** 发送消息（非流式，保留兼容） */
export async function sendMessage(
  conversationId: string,
  data: { content: string },
): Promise<Message> {
  const res = await client.post(`/chat/conversations/${conversationId}/messages`, data);
  return res.data;
}

/** 删除会话 */
export async function deleteConversation(id: string): Promise<void> {
  await client.delete(`/chat/conversations/${id}`);
}

/** 发送消息（流式 SSE） */
export async function sendMessageStream(
  conversationId: string,
  data: { content: string },
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: Error) => void,
): Promise<void> {
  const token = localStorage.getItem('token');
  const response = await fetch(
    `/api/chat/conversations/${conversationId}/messages/stream`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    },
  );

  if (!response.ok) {
    onError(new Error(`HTTP ${response.status}`));
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      // 保留最后一个可能不完整的行
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith('data:')) continue;
        const payload = trimmed.slice(5).trim();
        if (payload === '[DONE]') {
          onDone();
          return;
        }
        try {
          const parsed = JSON.parse(payload);
          if (parsed.error) {
            onError(new Error(parsed.error.message || 'Stream error'));
            return;
          }
          const choices = parsed.choices || [];
          for (const choice of choices) {
            const content = choice.delta?.content;
            if (content) {
              onChunk(content);
            }
          }
        } catch {
          // 跳过无法解析的行
        }
      }
    }
    // 流正常结束但没有收到 [DONE]
    onDone();
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)));
  }
}
