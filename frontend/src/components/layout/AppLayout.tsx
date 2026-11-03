import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import Sidebar from './Sidebar'

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="h-screen flex flex-col bg-canvas">
      <Navbar sidebarOpen={sidebarOpen} onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar open={sidebarOpen} />
        <main className="flex-1 overflow-auto bg-canvas">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
