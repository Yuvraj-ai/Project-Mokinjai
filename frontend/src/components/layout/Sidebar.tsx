import { useState, useRef, useCallback } from 'react'
import { NavLink } from 'react-router-dom'
import { GitBranch, Play, FileText, Bot, Braces, FolderOpen, Database, BookOpen, Wrench, Plug, Cpu } from 'lucide-react'
import { cn } from '../../lib/utils'

const navItems = [
  { to: '/agents', label: 'Agents', icon: Bot },
  { to: '/workflows', label: 'Workflows', icon: GitBranch },
  { to: '/executions', label: 'Executions', icon: Play },
  { to: '/prompts', label: 'System Prompts', icon: FileText },
  { to: '/structured-outputs', label: 'Structured Output', icon: Braces },
  { to: '/files', label: 'Files', icon: FolderOpen },
  { to: '/data-sources', label: 'Data Sources', icon: Database },
  { to: '/skills', label: 'Skills', icon: BookOpen },
  { to: '/llms', label: 'LLMs', icon: Cpu },
  { to: '/tools', label: 'Tools', icon: Wrench },
  { to: '/connectors', label: 'Connectors', icon: Plug },
]

const navSections = [
  { label: 'Build', items: navItems.slice(0, 5) },
  { label: 'Data & tools', items: navItems.slice(5) },
]

interface SidebarProps {
  open: boolean
}

export default function Sidebar({ open }: SidebarProps) {
  const [hoverExpanded, setHoverExpanded] = useState(false)
  const collapseTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

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
          className="fixed inset-0 bg-black/20 z-20 md:hidden"
          style={{ top: '3rem' }}
          data-od-id="sidebar-overlay"
        />
      )}
      <aside
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        className={cn(
          open ? 'translate-x-0' : '-translate-x-full',
          'md:translate-x-0',
          'fixed md:static top-12 left-0 z-20',
          isExpanded ? 'w-56' : 'w-14',
          'bg-surface border-r border-line',
          'flex flex-col shrink-0',
          'transition-all duration-200 ease-out',
          'h-[calc(100vh-3rem)]',
        )}
        data-od-id="sidebar"
      >
        <nav className="flex-1 px-2 py-4">
          <div className="space-y-1">
            {navSections.map((section) => (
              <div key={section.label} className="mb-4">
                {isExpanded && (
                  <p className="text-[11px] font-medium text-ink-subtle px-3 pb-1.5">
                    {section.label}
                  </p>
                )}
                <div className="space-y-0.5">
                  {section.items.map((item) => (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cn(
                          'flex items-center rounded-lg text-sm transition-colors duration-150',
                          isExpanded ? 'gap-2.5 px-3 py-2' : 'justify-center px-2 py-2.5',
                          isActive
                            ? 'bg-surface-muted text-ink font-medium'
                            : 'text-ink-muted hover:bg-surface-muted hover:text-ink',
                        )
                      }
                      title={!isExpanded ? item.label : undefined}
                      data-od-id={`nav-${item.to.replace('/', '').toLowerCase()}`}
                    >
                      <item.icon className="w-4 h-4 shrink-0" aria-hidden />
                      {isExpanded && <span>{item.label}</span>}
                    </NavLink>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </nav>
      </aside>
    </>
  )
}
