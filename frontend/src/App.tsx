import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import WorkflowEditorPage from './pages/WorkflowEditorPage'
import ExecutionHistoryPage from './pages/ExecutionHistoryPage'
import AppLayout from './components/layout/AppLayout'
import ProtectedRoute from './components/auth/ProtectedRoute'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/" element={<Navigate to="/workflows" replace />} />
        <Route path="/workflows" element={<DashboardPage />} />
        <Route path="/workflows/:workflowId/edit" element={<WorkflowEditorPage />} />
        <Route path="/executions" element={<ExecutionHistoryPage />} />
      </Route>
    </Routes>
  )
}
