import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import LoginForm from '../components/auth/LoginForm'

export default function LoginPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  if (isAuthenticated) return <Navigate to="/workflows" replace />

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{
        background: 'var(--bg-base)',
        backgroundImage: `
          radial-gradient(ellipse 80% 60% at 50% -10%, rgba(124,58,237,0.18) 0%, transparent 70%),
          radial-gradient(ellipse 40% 40% at 80% 80%, rgba(79,70,229,0.08) 0%, transparent 60%)
        `,
      }}
    >
      <LoginForm />
    </div>
  )
}
