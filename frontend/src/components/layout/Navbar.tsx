import { useState, useRef, useEffect } from 'react'
import { useAuthStore } from '../../store/authStore'
import { useAuth } from '../../hooks/useAuth'
import { useThemeStore } from '../../store/themeStore'
import { LogOut, ChevronDown, Menu, X, Sun, Moon } from 'lucide-react'
import Badge from '../ui/Badge'
import { MenuItem } from '../ui/Menu'
import { cn } from '../../lib/utils'

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
    <header
      className="h-12 bg-canvas border-b border-line flex items-center justify-between px-4 md:px-5 shrink-0 z-30"
      data-od-id="navbar"
    >
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          className="md:hidden p-1.5 rounded-lg hover:bg-surface-muted text-ink-muted transition-colors"
          data-od-id="sidebar-toggle"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <div className="w-7 h-7 bg-primary rounded-lg flex items-center justify-center" data-od-id="app-logo">
          <svg viewBox="0 0 24 24" className="w-4 h-4 text-primary-fg" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
            <path d="M12 2L7 8h3v6h4V8h3l-5-6z" />
          </svg>
        </div>
        <h1 className="text-sm font-semibold text-ink tracking-tight">
          Project Mokinjay
        </h1>
      </div>

      <div className="flex items-center gap-1.5">
        <button
          onClick={toggle}
          aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          className="p-2 rounded-lg hover:bg-surface-muted text-ink-muted transition-colors"
          title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          data-od-id="theme-toggle"
        >
          {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className={cn(
              'flex items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors duration-150',
              'hover:bg-surface-muted',
            )}
            data-od-id="user-menu"
          >
            <div className="w-7 h-7 bg-surface-muted border border-line text-ink rounded-full flex items-center justify-center text-xs font-semibold relative">
              {initials}
            </div>
            <span className="text-sm text-ink-muted hidden sm:block max-w-[160px] truncate">
              {user?.email ?? 'User'}
            </span>
            {user?.is_superuser && (
              <span className="hidden sm:block">
                <Badge variant="outline">Admin</Badge>
              </span>
            )}
            <ChevronDown className="w-4 h-4 text-ink-subtle" />
          </button>

          {menuOpen && (
            <div
              className="absolute right-0 mt-2 w-56 bg-surface-raised border border-line rounded-xl shadow-menu py-1 z-50 animate-scale-in"
              data-od-id="user-dropdown"
            >
              <div className="px-4 py-3 border-b border-line">
                <p className="text-sm font-medium text-ink truncate">{user?.name ?? 'User'}</p>
                <p className="text-xs text-ink-subtle truncate">{user?.email}</p>
                {user?.is_superuser && (
                  <p className="mt-1.5">
                    <Badge variant="outline">Superuser</Badge>
                  </p>
                )}
              </div>
              <MenuItem
                icon={LogOut}
                destructive
                data-od-id="logout-button"
                onClick={() => {
                  setMenuOpen(false)
                  logout()
                }}
              >
                Sign out
              </MenuItem>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
