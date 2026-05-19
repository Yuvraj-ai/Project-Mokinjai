import { useState, useRef, useEffect } from 'react'
import { useAuthStore } from '../../store/authStore'
import { useAuth } from '../../hooks/useAuth'
import { LogOut, ChevronDown, Zap } from 'lucide-react'

export default function Navbar() {
  const user = useAuthStore((state) => state.user)
  const { logout } = useAuth()
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
    ? user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : (user?.email?.[0]?.toUpperCase() ?? 'U')

  return (
    <header
      className="h-14 flex items-center justify-between px-5 shrink-0 z-30"
      style={{
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
      }}
    >
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg, var(--accent-from), var(--accent-to))' }}
        >
          <Zap className="w-4 h-4 text-white" fill="white" />
        </div>
        <span
          className="text-base font-bold tracking-tight"
          style={{ color: 'var(--text-primary)' }}
        >
          Mokin<span style={{ color: 'var(--accent-mid)' }}>jay</span>
        </span>
        <span
          className="text-[10px] font-semibold px-1.5 py-0.5 rounded"
          style={{
            background: 'rgba(99,102,241,0.15)',
            color: 'var(--accent-mid)',
            border: '1px solid rgba(99,102,241,0.25)',
            letterSpacing: '0.06em',
          }}
        >
          BETA
        </span>
      </div>

      {/* User menu */}
      <div className="relative" ref={menuRef}>
        <button
          id="navbar-user-menu"
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 transition-all"
          style={{ color: 'var(--text-secondary)' }}
          onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-hover)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
        >
          <div
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
            style={{
              background: 'linear-gradient(135deg, var(--accent-from), var(--accent-to))',
              color: '#fff',
            }}
          >
            {initials}
          </div>
          <span
            className="text-sm font-medium hidden sm:block max-w-[140px] truncate"
            style={{ color: 'var(--text-secondary)' }}
          >
            {user?.email ?? 'User'}
          </span>
          <ChevronDown
            className="w-3.5 h-3.5 transition-transform"
            style={{
              color: 'var(--text-muted)',
              transform: menuOpen ? 'rotate(180deg)' : 'none',
            }}
          />
        </button>

        {menuOpen && (
          <div
            className="absolute right-0 mt-2 w-56 rounded-xl py-1 z-50 animate-fade-in glass-strong"
            style={{ boxShadow: 'var(--shadow-lg)' }}
          >
            <div
              className="px-4 py-3"
              style={{ borderBottom: '1px solid var(--border-subtle)' }}
            >
              <p className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                {user?.name ?? 'User'}
              </p>
              <p className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                {user?.email}
              </p>
            </div>
            <button
              id="navbar-logout-btn"
              onClick={() => { setMenuOpen(false); logout() }}
              className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors"
              style={{ color: '#f87171' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'rgba(239,68,68,0.08)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              <LogOut className="w-4 h-4" />
              Sign out
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
