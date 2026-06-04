import client from './client';
import type { Conversation, Message, PaginatedResponse } from '../types';

/** 会话列表 */
export async function listConversations(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Conversation>> {
  const res = await client.get('/chat/conversations', { params });
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

/** 获取消息列表 */
export async function getMessages(
  conversationId: number,
  params?: { page?: number; page_size?: number },
): Promise<PaginatedResponse<Message>> {
  const res = await client.get(`/chat/conversations/${conversationId}/messages`, {
    params,
  });
  return res.data;
}

/** 发送消息 */
export async function sendMessage(
  conversationId: number,
  data: { content: string },
): Promise<Message> {
  const res = await client.post(`/chat/conversations/${conversationId}/messages`, data);
  return res.data;
}

/** 删除会话 */
export async function deleteConversation(id: number): Promise<void> {
  await client.delete(`/chat/conversations/${id}`);
}
