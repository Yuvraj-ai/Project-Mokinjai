import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import WorkflowEditorPage from './pages/WorkflowEditorPage'
import ExecutionHistoryPage from './pages/ExecutionHistoryPage'
import PromptsPage from './pages/PromptsPage'
import LlmProfilesPage from './pages/LlmProfilesPage'
import StructuredOutputsPage from './pages/StructuredOutputsPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import SkillsPage from './pages/SkillsPage'
import ToolsPage from './pages/ToolsPage'
import ConnectorsPage from './pages/ConnectorsPage'
import AppLayout from './components/layout/AppLayout'
import ProtectedRoute from './components/auth/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/" element={<Navigate to="/workflows" replace />} />
        <Route path="/workflows" element={<DashboardPage />} />
        <Route path="/workflows/:workflowId/edit" element={<WorkflowEditorPage />} />
        <Route path="/executions" element={<ExecutionHistoryPage />} />
        <Route path="/prompts" element={<PromptsPage />} />
        <Route path="/structured-outputs" element={<StructuredOutputsPage />} />
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/llms" element={<LlmProfilesPage />} />
        <Route path="/tools" element={<ToolsPage />} />
        <Route path="/connectors" element={<ConnectorsPage />} />
      </Route>
    </Routes>
  )
}
