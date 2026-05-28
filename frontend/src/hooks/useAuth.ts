import { useEffect, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { loginApi, getMe } from '../api/auth'

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

  return {
    user,
    isAuthenticated,
    login: handleLogin,
    logout,
  }
}
