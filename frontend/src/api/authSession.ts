import axios from 'axios'
import { useAuthStore } from '../store/authStore'

/**
 * The one place auth-death is handled (root-cause fix for the login bounce:
 * the Axios interceptor and the raw-fetch stream clients used to have three
 * different 401 policies — none shared, none updating the auth store, the
 * fetch ones never even clearing the dead tokens).
 */

let refreshInFlight: Promise<boolean> | null = null

/**
 * One refresh attempt shared by every concurrent 401. Previously each failing
 * request fired its own POST /api/auth/refresh — a storm of identical calls on
 * every page load with a dead session. Resolves true only if new tokens were
 * stored; never throws.
 */
export function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    const refreshToken = localStorage.getItem('refresh_token')
    if (!refreshToken) return Promise.resolve(false)
    refreshInFlight = axios
      .post(`${import.meta.env.VITE_API_URL || ''}/api/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then(({ data }) => {
        localStorage.setItem('access_token', data.access_token)
        localStorage.setItem('refresh_token', data.refresh_token)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshInFlight = null
      })
  }
  return refreshInFlight
}

/**
 * The session is over: clear credentials and the auth store so the router —
 * not a hard reload — lands on /login exactly once. Idempotent: once the
 * store is signed out, calling this again does nothing.
 */
export function handleAuthFailure(): void {
  const store = useAuthStore.getState()
  if (!store.isAuthenticated && !localStorage.getItem('access_token')) return
  store.forceSignOut()
}
