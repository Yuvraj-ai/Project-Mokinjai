import { NavLink } from 'react-router-dom'
import { GitBranch, History } from 'lucide-react'

const navItems = [
  { to: '/workflows', label: 'Workflows', icon: GitBranch },
  { to: '/executions', label: 'Executions', icon: History },
]

export default function Sidebar() {
  return (
    <aside
      className="w-52 flex flex-col shrink-0"
      style={{
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
      }}
    >
      <nav className="flex-1 px-2.5 py-4 space-y-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all"
            style={({ isActive }) =>
              isActive
                ? {
                    background: 'rgba(99,102,241,0.15)',
                    color: '#a5b4fc',
                    borderLeft: '2px solid var(--accent-mid)',
                    paddingLeft: '10px',
                  }
                : {
                    color: 'var(--text-muted)',
                    borderLeft: '2px solid transparent',
                    paddingLeft: '10px',
                  }
            }
            onMouseEnter={e => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) {
                el.style.background = 'var(--bg-hover)'
                el.style.color = 'var(--text-secondary)'
              }
            }}
            onMouseLeave={e => {
              const el = e.currentTarget
              if (!el.getAttribute('aria-current')) {
                el.style.background = 'transparent'
                el.style.color = 'var(--text-muted)'
              }
            }}
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className="w-4 h-4 shrink-0"
                  style={{ color: isActive ? 'var(--accent-mid)' : 'inherit' }}
                />
                {item.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom hint */}
      <div
        className="px-4 py-4 text-[10px] leading-relaxed"
        style={{
          color: 'var(--text-disabled)',
          borderTop: '1px solid var(--border-subtle)',
        }}
      >
        Mokinjay AI Agent Builder
        <br />
        <span style={{ color: 'var(--text-muted)' }}>v0.1.0-beta</span>
      </div>
    </aside>
  )
}
