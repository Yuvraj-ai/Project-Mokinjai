import { useEffect, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { loginApi, getMe } from '../api/auth'
import { validateAdminOTP } from '../api/otp'

export function useAuth() {
  const { user, isAuthenticated, setUser, login, logout } = useAuthStore()

  useEffect(() => {
    if (isAuthenticated && !user) {
      getMe()
        .then(setUser)
        .catch(() => logout())
    }
  }, [isAuthenticated, user, setUser, logout])

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
