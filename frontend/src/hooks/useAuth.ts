import { useEffect, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { loginApi, getMe } from '../api/auth'
import { validateAdminOTP } from '../api/otp'

export function useAuth() {
  const { user, isAuthenticated, setUser, login, logout, forceSignOut } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated && !user) {
      getMe()
        .then(setUser)
        .catch((caught) => {
          // Only a real auth failure ends the session — a network blip or a
          // restarting backend must not log the user out.
          if ((caught as { response?: { status?: number } })?.response?.status === 401) {
            forceSignOut()
          }
        })
    }
  }, [isAuthenticated, user, setUser, logout, forceSignOut])

  // A dead session cannot announce itself: an idle tab would keep rendering the
  // signed-in shell forever. Probe on focus and once a minute, and treat a 401
  // (after the interceptor's one refresh attempt) as the end of the session.
  useEffect(() => {
    if (!isAuthenticated) return

    const probe = () => {
      getMe()
        .then(setUser)
        .catch((caught) => {
          if ((caught as { response?: { status?: number } })?.response?.status === 401) {
            forceSignOut()
          }
        })
    }
    const onVisible = () => {
      if (document.visibilityState === 'visible') probe()
    }

    const timer = window.setInterval(probe, 60_000)
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)

    // Signing out in another tab clears the tokens; mirror that here.
    const onStorage = (event: StorageEvent) => {
      if (event.key === 'access_token' && !event.newValue) forceSignOut()
    }
    window.addEventListener('storage', onStorage)

    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
      window.removeEventListener('storage', onStorage)
    }
  }, [isAuthenticated, setUser, forceSignOut])

  const handleLogin = useCallback(
    async (email: string, password: string) => {
      const tokens = await loginApi(email, password)
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)
      const userData = await getMe()
      login(userData, tokens.access_token, tokens.refresh_token)
      return userData
    },
    [login]
  )

  const handleAdminOTPLogin = useCallback(
    async (sessionToken: string, code: string) => {
      const result = await validateAdminOTP(sessionToken, code)
      localStorage.setItem('access_token', result.access_token)
      localStorage.setItem('refresh_token', result.refresh_token)
      const userData = await getMe()
      login(userData, result.access_token, result.refresh_token)
      return userData
    },
    [login]
  )

  return {
    user,
    isAuthenticated,
    login: handleLogin,
    adminOtpLogin: handleAdminOTPLogin,
    logout,
  }
}
