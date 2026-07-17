import axios from 'axios'

/**
 * Shared Axios client pointed at the FastAPI backend.
 * Vite proxies `/api` → `http://localhost:8000` in development.
 */
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120_000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ??
      error.message ??
      'Une erreur réseau est survenue'
    return Promise.reject(new Error(typeof message === 'string' ? message : 'Erreur API'))
  },
)
