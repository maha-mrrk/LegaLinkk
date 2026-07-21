import axios from 'axios'

/**
 * Shared Axios client pointed at the backend API.
 * Vite proxies `/api` → `http://localhost:8000` in development.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 300_000,
})

const TOKEN_KEY = 'legallink_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

// Attach the bearer token to every request when present.
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    // Session expired / unauthenticated → clear token and bounce to login.
    if (status === 401 && !error.config?.url?.includes('/auth/')) {
      setToken(null)
      if (window.location.pathname !== '/login') {
        window.location.assign('/login')
      }
    }
    const message =
      error.response?.data?.detail ??
      error.message ??
      'Une erreur réseau est survenue'
    return Promise.reject(new Error(typeof message === 'string' ? message : 'Erreur API'))
  },
)
