import { useState, useRef, useEffect } from 'react'
import { useAuthStore } from '../../store/authStore'
import { useAuth } from '../../hooks/useAuth'
import { useThemeStore } from '../../store/themeStore'
import { LogOut, ChevronDown, Shield, Menu, X, Sun, Moon } from 'lucide-react'

interface NavbarProps {
  sidebarOpen: boolean
  onToggleSidebar: () => void
}

export default function Navbar({ sidebarOpen, onToggleSidebar }: NavbarProps) {
  const user = useAuthStore((state) => state.user)
  const { logout } = useAuth()
  const { dark, toggle } = useThemeStore()
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const initials = user?.name
    ? user.name
        .split(' ')
        .map((n: string) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : (user?.email?.[0]?.toUpperCase() ?? 'U')

  return (
    <header className="h-14 bg-white/80 dark:bg-ink-800/80 backdrop-blur-sm border-b border-ink-100/60 dark:border-ink-700/60 flex items-center justify-between px-4 md:px-6 shrink-0 z-30">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-1.5 rounded-lg hover:bg-ink-50 dark:hover:bg-ink-700 text-ink-500 dark:text-ink-300 transition-colors"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <div className="w-8 h-8 bg-ink-800 dark:bg-cream-200 rounded-lg flex items-center justify-center shadow-sm">
          <span className="text-cream-50 dark:text-ink-800 text-sm font-bold leading-none">◆</span>
        </div>
        <h1 className="text-base font-display text-ink-800 dark:text-cream-100 tracking-tight">
          Project Mokinjay
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={toggle}
          className="p-2 rounded-lg hover:bg-ink-50 dark:hover:bg-ink-700 text-ink-400 dark:text-ink-300 transition-colors"
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex items-center gap-2.5 hover:bg-cream-100 dark:hover:bg-ink-700 rounded-lg px-3 py-2 transition-all duration-200"
          >
            <div className="w-8 h-8 bg-cream-200 dark:bg-ink-600 text-ink-700 dark:text-cream-200 rounded-full flex items-center justify-center text-sm font-semibold relative">
              {initials}
              {user?.is_superuser && (
                <Shield className="w-3 h-3 text-accent absolute -top-1 -right-1" />
              )}
            </div>
            <span className="text-sm text-ink-600 dark:text-ink-300 font-body hidden sm:block max-w-[160px] truncate">
              {user?.email ?? 'User'}
            </span>
            {user?.is_superuser && (
              <span className="text-xs bg-cream-200 dark:bg-ink-600 text-accent px-2 py-0.5 rounded-full font-semibold hidden sm:block">
                Admin
              </span>
            )}
            <ChevronDown className="w-4 h-4 text-ink-300" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-ink-800 rounded-xl shadow-lg border border-ink-100/60 dark:border-ink-700/60 py-1 z-50 animate-scale-in">
              <div className="px-4 py-3 border-b border-ink-100/60 dark:border-ink-700/60">
                <p className="text-sm font-medium text-ink-900 dark:text-cream-100 truncate">{user?.name ?? 'User'}</p>
                <p className="text-xs text-ink-400 truncate">{user?.email}</p>
                {user?.is_superuser && (
                  <p className="text-xs text-accent font-semibold mt-1 flex items-center gap-1">
                    <Shield className="w-3 h-3" /> Superuser
                  </p>
                )}
              </div>
              <button
                onClick={() => {
                  setMenuOpen(false)
                  logout()
                }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-status-error hover:bg-cream-100 dark:hover:bg-ink-700 transition-colors duration-200"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
