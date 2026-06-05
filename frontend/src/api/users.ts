import client from './client';
import type { User, Role, Department } from '../types';

// ---- 用户 ----

/** 用户列表（后端返回数组） */
export async function listUsers(): Promise<User[]> {
  const res = await client.get('/users');
  return res.data;
}

/** 创建用户 */
export async function createUser(data: {
  username: string;
  password: string;
  email: string;
  role_id: string;
  department_id?: string;
}): Promise<User> {
  const res = await client.post('/users', data);
  return res.data;
}

/** 更新用户 */
export async function updateUser(id: string, data: Partial<User>): Promise<User> {
  const res = await client.put(`/users/${id}`, data);
  return res.data;
}

/** 删除用户 */
export async function deleteUser(id: string): Promise<void> {
  await client.delete(`/users/${id}`);
}

// ---- 角色 ----

/** 角色列表 */
export async function listRoles(): Promise<Role[]> {
  const res = await client.get('/users/roles');
  return res.data;
}

// ---- 部门 ----

/** 部门列表 */
export async function listDepartments(): Promise<Department[]> {
  const res = await client.get('/users/departments');
  return res.data;
}

/** 创建部门 */
export async function createDepartment(data: Partial<Department>): Promise<Department> {
  const res = await client.post('/users/departments', data);
  return res.data;
}

/** 更新部门 */
export async function updateDepartment(id: string, data: Partial<Department>): Promise<Department> {
  const res = await client.put(`/users/departments/${id}`, data);
  return res.data;
}

/** 删除部门 */
export async function deleteDepartment(id: string): Promise<void> {
  await client.delete(`/users/departments/${id}`);
}
