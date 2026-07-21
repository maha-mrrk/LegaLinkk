import { api, setToken } from './api'

export interface AuthUser {
  id: string
  email: string
  full_name: string | null
  role: string
  is_active: boolean
  created_at: string
}

interface TokenResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const { data } = await api.post<TokenResponse>('/auth/login', { email, password })
  setToken(data.access_token)
  return data.user
}

export async function register(payload: {
  email: string
  password: string
  full_name?: string
  role?: string
}): Promise<AuthUser> {
  const { data } = await api.post<TokenResponse>('/auth/register', payload)
  setToken(data.access_token)
  return data.user
}

export async function fetchMe(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>('/auth/me')
  return data
}

export function logout(): void {
  setToken(null)
}

/** Two-letter initials derived from a name or email. */
export function initialsFor(user: Pick<AuthUser, 'full_name' | 'email'>): string {
  const source = user.full_name?.trim() || user.email
  const cleaned = source.replace(/^(me\.?|maître|maitre|mr\.?|mme\.?|dr\.?)\s+/i, '')
  const parts = cleaned.split(/[\s@.]+/).filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return cleaned.slice(0, 2).toUpperCase()
}
