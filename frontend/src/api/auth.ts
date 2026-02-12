import apiClient from './client'
import type { User } from '../store/authStore'

interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export async function loginApi(email: string, password: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/api/auth/login', { email, password })
  return response.data
}

export async function registerApi(email: string, password: string, name?: string): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/api/auth/register', { email, password, name })
  return response.data
}

export async function getMe(): Promise<User> {
  const response = await apiClient.get<User>('/api/auth/me')
  return response.data
}
