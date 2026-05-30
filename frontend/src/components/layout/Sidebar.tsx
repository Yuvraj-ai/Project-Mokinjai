import { useState, useRef, useCallback } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { GitBranch, Play, FileText } from 'lucide-react'

const navItems = [
  { to: '/workflows', label: 'Workflows', icon: GitBranch },
  { to: '/executions', label: 'Executions', icon: Play },
  { to: '/prompts', label: 'System Prompts', icon: FileText },
]

interface SidebarProps {
  open: boolean
}

export default function Sidebar({ open }: SidebarProps) {
  const [hoverExpanded, setHoverExpanded] = useState(false)
  const collapseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const location = useLocation()

  const handleMouseEnter = useCallback(() => {
    if (collapseTimer.current) {
      clearTimeout(collapseTimer.current)
      collapseTimer.current = null
    }
    setHoverExpanded(true)
  }, [])

  const handleMouseLeave = useCallback(() => {
    collapseTimer.current = setTimeout(() => {
      setHoverExpanded(false)
    }, 150)
  }, [])

  const isExpanded = hoverExpanded

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 bg-ink-900/20 z-20 md:hidden"
          style={{ top: '3.5rem' }}
        />
      )}
      <aside
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className={`
          ${open ? 'translate-x-0' : '-translate-x-full'}
          md:translate-x-0
          fixed md:static top-14 left-0 z-20
          ${isExpanded ? 'w-56' : 'w-16'}
          bg-white dark:bg-ink-800
          border-r border-ink-100/60 dark:border-ink-700/60
          flex flex-col shrink-0
          transition-all duration-200 ease-out
          h-[calc(100vh-3.5rem)]
        `}
      >
        <nav className="flex-1 px-2 py-3">
          <div className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg text-sm font-body font-medium transition-all duration-150 ${
                    isExpanded ? 'px-4 py-3' : 'justify-center px-2 py-3'
                  } ${
                    isActive
                      ? 'bg-ink-800/5 dark:bg-ink-600/50 text-ink-900 dark:text-cream-100'
                      : 'text-ink-400 dark:text-ink-300 hover:bg-ink-50 dark:hover:bg-ink-700 hover:text-ink-700 dark:hover:text-cream-200'
                  }`
                }
                title={!isExpanded ? item.label : undefined}
              >
                <item.icon className="w-5 h-5 shrink-0" />
                {isExpanded && <span>{item.label}</span>}
              </NavLink>
            ))}
          </div>
        </nav>
      </aside>
    </>
  )
}
