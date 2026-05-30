import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import LoginForm from '../components/auth/LoginForm'
import AdminOTPLogin from '../components/auth/AdminOTPLogin'

export default function LoginPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)

  if (isAuthenticated) {
    return <Navigate to="/workflows" replace />
  }

  return (
    <div className="min-h-screen bg-cream-50 dark:bg-ink-900 flex">
      {/* Left: Editorial brand showcase */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-ink-900 dark:bg-ink-950 overflow-hidden">
        <div className="grain-overlay" />
        <div className="relative z-10 flex flex-col justify-center px-16 xl:px-24">
          <p className="text-accent-muted text-sm tracking-[0.3em] uppercase mb-6 animate-fade-in">
            Intelligent Automation
          </p>
          <h1 className="font-display italic text-cream-50 text-6xl xl:text-7xl leading-[0.95] mb-8 animate-fade-in-up stagger-1">
            Mokinjay
          </h1>
          <div className="editorial-rule-left mb-8 animate-fade-in-up stagger-2" />
          <p className="text-cream-200/70 text-lg max-w-md leading-relaxed animate-fade-in-up stagger-3">
            Build, orchestrate, and deploy AI agents with surgical precision.
            A workspace designed for builders who value clarity.
          </p>
          <div className="mt-16 flex items-center gap-3 animate-fade-in-up stagger-4">
            <div className="w-8 h-px bg-accent" />
            <span className="text-accent-muted text-xs tracking-widest uppercase">
              Agent Builder
            </span>
          </div>
        </div>
        {/* Decorative diagonal line */}
        <div className="absolute bottom-0 right-0 w-px h-2/3 bg-gradient-to-t from-accent/20 to-transparent origin-bottom-right -rotate-12" />
      </div>

      {/* Right: Login form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 lg:px-16">
        <div className="w-full max-w-md animate-fade-in">
          {/* Mobile-only brand */}
          <div className="lg:hidden mb-10 text-center">
            <h1 className="font-display italic text-ink-900 dark:text-cream-100 text-4xl mb-2">
              Mokinjay
            </h1>
            <p className="text-ink-500/60 dark:text-ink-400 text-xs tracking-[0.25em] uppercase">
              Agent Builder
            </p>
          </div>

          <LoginForm />
          <AdminOTPLogin />
        </div>
      </div>
    </div>
  )
}
