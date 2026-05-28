export interface User {
  id: string
  email: string
  name: string | null
  avatar_url: string | null
  is_superuser: boolean
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}
