import { create } from 'zustand'

interface ThemeState {
  dark: boolean
  toggle: () => void
  setDark: (dark: boolean) => void
}

const getInitialDark = (): boolean => {
  if (typeof window === 'undefined') return false
  const stored = localStorage.getItem('mokinjay-theme')
  if (stored) return stored === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export const useThemeStore = create<ThemeState>()((set) => ({
  dark: getInitialDark(),
  toggle: () =>
    set((state) => {
      const next = !state.dark
      localStorage.setItem('mokinjay-theme', next ? 'dark' : 'light')
      if (next) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
      return { dark: next }
    }),
  setDark: (dark: boolean) => {
    localStorage.setItem('mokinjay-theme', dark ? 'dark' : 'light')
    if (dark) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    set({ dark })
  },
}))

// Apply on load
if (typeof window !== 'undefined' && getInitialDark()) {
  document.documentElement.classList.add('dark')
}
