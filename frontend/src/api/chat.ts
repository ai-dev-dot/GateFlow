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

/** 发送消息 */
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
