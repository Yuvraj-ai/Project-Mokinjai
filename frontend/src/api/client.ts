import axios from 'axios'
import { handleAuthFailure, refreshAccessToken } from './authSession'

// No Content-Type here on purpose. Axios sets `application/json` itself for an object
// body, while a FormData body must be left alone so the browser can add the multipart
// boundary — and a hand-set `multipart/form-data` without a boundary makes the request
// body unparseable on the server, which is exactly the bug this omission prevents.
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// A 401 from the auth endpoints is an answer (wrong password, dead refresh
// token), not an expired session — refreshing and retrying there caused the
// login page to reload itself and churn tokens.
function isAuthEndpoint(url: string | undefined): boolean {
  return !!url && url.includes('/api/auth/')
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthEndpoint(originalRequest.url)
    ) {
      originalRequest._retry = true
      // One shared refresh for every concurrent 401; the callers queue on the
      // same promise instead of each firing their own POST /api/auth/refresh.
      if (await refreshAccessToken()) {
        originalRequest.headers.Authorization = `Bearer ${localStorage.getItem('access_token')}`
        return apiClient(originalRequest)
      }
      // Session over: clear credentials and the auth store once. ProtectedRoute
      // then navigates to /login — no hard reload, no repeated redirects.
      handleAuthFailure()
    }
    return Promise.reject(error)
  }
)

/** The `detail` a FastAPI error carries, when there is one. */
export function axiosDetail(error: unknown): string | null {
  if (!error || typeof error !== 'object' || !('response' in error)) return null
  const response = (error as { response?: { data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  return typeof detail === 'string' ? detail : null
}

export default apiClient
