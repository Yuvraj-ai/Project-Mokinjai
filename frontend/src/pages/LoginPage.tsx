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
      <div className="hidden lg:flex lg:w-1/2 relative bg-[#262334] border-r border-line flex-col justify-end p-12 xl:p-16 overflow-hidden">
        {/* Mokinjay Dither Illustration fitting full height without getting cut */}
        <div className="absolute inset-0 flex items-center justify-center select-none pointer-events-none">
          <img
            src="/ditther-1794604960622.png"
            alt="Mokinjay Illustration"
            className="w-full h-full object-contain"
            style={{
              maskImage:
                'linear-gradient(to right, transparent 0%, black 4%, black 96%, transparent 100%), linear-gradient(to bottom, transparent 0%, black 3%, black 97%, transparent 100%)',
              WebkitMaskImage:
                'linear-gradient(to right, transparent 0%, black 4%, black 96%, transparent 100%), linear-gradient(to bottom, transparent 0%, black 3%, black 97%, transparent 100%)',
              maskComposite: 'intersect',
              WebkitMaskComposite: 'destination-in',
            }}
          />
        </div>

        {/* Text moved to bottom left */}
        <div className="relative z-10 flex flex-col justify-end pt-2">
          <p className="text-[#A8A49C] text-xs font-mono tracking-[0.25em] uppercase mb-3 animate-fade-in">
            Intelligent Automation
          </p>
          <h1 className="text-4xl xl:text-5xl font-semibold text-[#FFFFFF] leading-[1.05] tracking-tight mb-4 animate-fade-in-up stagger-1">
            Mokinjay
          </h1>
          <div className="h-px w-20 bg-[#FFFFFF]/20 mb-4 animate-fade-in-up stagger-2" />
          <p className="text-[#FFFFFF]/70 text-sm xl:text-base max-w-md leading-relaxed mb-6 animate-fade-in-up stagger-3">
            Build, orchestrate, and deploy AI agents with surgical precision.
            A workspace designed for builders who value clarity.
          </p>
          <div className="flex items-center gap-3 animate-fade-in-up stagger-4">
            <span className="font-mono text-xs uppercase tracking-widest text-[#FFFFFF]/50">
              Agent Builder
            </span>
          </div>
        </div>
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
