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
    <div className="min-h-screen bg-canvas flex">
      {/* Left: brand panel (stays dark in both themes) */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-[#141414] border-r border-line flex-col overflow-hidden">
        <div className="relative z-10 flex flex-col justify-center px-16 xl:px-24">
          <p className="text-[#A8A49C] text-xs font-mono tracking-[0.25em] uppercase mb-8 animate-fade-in">
            Intelligent Automation
          </p>
          <h1 className="text-6xl xl:text-7xl font-semibold text-[#FFFFFF] leading-[1.02] tracking-tight mb-8 animate-fade-in-up stagger-1">
            Mokinjay
          </h1>
          <div className="h-px w-24 bg-[#FFFFFF]/20 mb-8 animate-fade-in-up stagger-2" />
          <p className="text-[#FFFFFF]/60 text-lg max-w-md leading-relaxed animate-fade-in-up stagger-3">
            Build, orchestrate, and deploy AI agents with surgical precision.
            A workspace designed for builders who value clarity.
          </p>
          <div className="mt-16 flex items-center gap-3 animate-fade-in-up stagger-4">
            <span className="font-mono text-xs uppercase tracking-widest text-[#FFFFFF]/40">
              Agent Builder
            </span>
          </div>
        </div>
        {/* Quiet grid backdrop */}
        <div
          className="absolute inset-0 opacity-[0.05] pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
            backgroundSize: '72px 72px',
          }}
          aria-hidden
        />
      </div>

      {/* Right: Login form */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 lg:px-16">
        <div className="w-full max-w-md animate-fade-in">
          {/* Mobile-only brand */}
          <div className="lg:hidden mb-10 text-center">
            <div className="mx-auto mb-4 w-10 h-10 bg-[#141414] rounded-lg flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-5 h-5 text-[#FFFFFF]" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" aria-hidden="true">
                <path d="M12 2L7 8h3v6h4V8h3l-5-6z" />
              </svg>
            </div>
            <h1 className="text-2xl font-semibold text-ink tracking-tight">Mokinjay</h1>
            <p className="mt-1 font-mono text-[11px] uppercase tracking-widest text-ink-subtle">
              Agent Builder
            </p>
          </div>

          <div className="bg-surface border border-line rounded-2xl px-8 py-9">
            <LoginForm />
            <AdminOTPLogin />
          </div>
        </div>
      </div>
    </div>
  )
}
