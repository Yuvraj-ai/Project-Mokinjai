import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ReactFlowProvider } from '@xyflow/react'
import Canvas from '../components/flow/Canvas'
import ModuleLibrary from '../components/flow/sidebar/ModuleLibrary'
import PropertiesPanel from '../components/flow/sidebar/PropertiesPanel'
import CanvasToolbar from '../components/flow/toolbar/CanvasToolbar'
import ExecutionPanel from '../components/execution/ExecutionPanel'
import { useWorkflowStore } from '../store/workflowStore'
import { useExecutionStore } from '../store/executionStore'
import { getWorkflow } from '../api/workflows'
import { listWorkspaces } from '../api/workspaces'

export default function WorkflowEditorPage() {
  const { workflowId } = useParams<{ workflowId: string }>()
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const { setWorkflowMeta, setNodes, setEdges, markClean, selectedNodeId } = useWorkflowStore()
  const { currentExecution } = useExecutionStore()

  useEffect(() => {
    async function load() {
      try {
        const workspaces = await listWorkspaces()
        if (workspaces.length > 0 && workflowId) {
          const wsId = workspaces[0].id
          setWorkspaceId(wsId)
          const workflow = await getWorkflow(wsId, workflowId)
          setWorkflowMeta(workflow.id, workflow.name, workflow.description || '')
          const flowDef = workflow.flow_definition || { nodes: [], edges: [] }
          setNodes(
            (flowDef.nodes || []).map((n: any) => ({
              id: n.id,
              type: n.type,
              position: n.position,
              data: n.data || {},
            }))
          )
          setEdges(
            (flowDef.edges || []).map((e: any) => ({
              id: e.id,
              source: e.source,
              target: e.target,
              sourceHandle: e.sourceHandle || null,
              targetHandle: e.targetHandle || null,
            }))
          )
          markClean()
        }
      } catch (err) {
        console.error('Failed to load workflow:', err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [workflowId, setWorkflowMeta, setNodes, setEdges, markClean])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    )
  }

  return (
    <ReactFlowProvider>
      <div className="flex flex-col h-full">
        {workspaceId && workflowId && (
          <CanvasToolbar workspaceId={workspaceId} workflowId={workflowId} />
        )}
        <div className="flex flex-1 overflow-hidden">
          <ModuleLibrary />
          <div className="flex-1 relative">
            <Canvas />
          </div>
          {selectedNodeId && <PropertiesPanel />}
          {currentExecution && <ExecutionPanel />}
        </div>
      </div>
    </ReactFlowProvider>
  )
}
