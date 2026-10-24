import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="min-h-screen bg-cream-50 text-ink-800 dark:bg-ink-900 dark:text-cream-50">
      <Navbar sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      <div className="flex min-h-[calc(100vh-4rem)]">
        <Sidebar open={sidebarOpen} />
        <main className="min-w-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_top_right,_rgba(196,149,106,0.09),_transparent_32rem)] dark:bg-[radial-gradient(circle_at_top_right,_rgba(196,149,106,0.08),_transparent_32rem)]">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
