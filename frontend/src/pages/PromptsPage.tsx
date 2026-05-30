import { useState, useEffect } from 'react'
import { listWorkspaces } from '../api/workspaces'
import PromptLibrary from '../components/flow/sidebar/PromptLibrary'

export default function PromptsPage() {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)

  useEffect(() => {
    listWorkspaces().then((ws) => {
      if (ws && ws.length > 0) setWorkspaceId(ws[0].id)
    }).catch(() => {})
  }, [])

  if (!workspaceId) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-6 w-6 border-2 border-ink-200 border-t-accent" />
      </div>
    )
  }

  return (
    <div className="h-full">
      <PromptLibrary workspaceId={workspaceId} fullPage />
    </div>
  )
}
