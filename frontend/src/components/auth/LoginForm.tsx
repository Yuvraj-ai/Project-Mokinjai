import { useState, FormEvent } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { Mail, Lock, AlertCircle, ArrowRight } from 'lucide-react'

export default function LoginForm() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await login(email, password)
    } catch (err: any) {
      setError(
        err?.response?.data?.detail ||
          err?.message ||
          'Login failed. Please check your credentials.'
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full">
      <div className="mb-10">
        <h2 className="font-display text-3xl text-ink-900 dark:text-cream-100 mb-2 animate-fade-in-up">
          Welcome back
        </h2>
        <p className="text-ink-500 dark:text-ink-300 text-sm animate-fade-in-up stagger-1">
          Sign in to continue to your workspace
        </p>
      </div>

      {error && (
        <div className="mb-8 flex items-start gap-3 bg-status-error/5 border border-status-error/20 text-status-error rounded-sm px-4 py-3 text-sm animate-fade-in">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="animate-fade-in-up stagger-2">
          <label
            htmlFor="email"
            className="block text-xs font-medium text-ink-500 dark:text-ink-300 tracking-widest uppercase mb-3"
          >
            Email
          </label>
          <div className="relative">
            <Mail className="absolute left-0 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400 dark:text-ink-400" />
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="w-full pl-7 pr-0 py-3 bg-transparent border-b border-ink-200 dark:border-ink-600 text-ink-900 dark:text-cream-100 text-sm placeholder:text-ink-400 dark:placeholder:text-ink-500 focus:outline-none focus:border-accent-warm transition-colors duration-300"
            />
          </div>
        </div>

        <div className="animate-fade-in-up stagger-3">
          <label
            htmlFor="password"
            className="block text-xs font-medium text-ink-500 dark:text-ink-300 tracking-widest uppercase mb-3"
          >
            Password
          </label>
          <div className="relative">
            <Lock className="absolute left-0 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-400 dark:text-ink-400" />
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
              className="w-full pl-7 pr-0 py-3 bg-transparent border-b border-ink-200 dark:border-ink-600 text-ink-900 dark:text-cream-100 text-sm placeholder:text-ink-400 dark:placeholder:text-ink-500 focus:outline-none focus:border-accent-warm transition-colors duration-300"
            />
          </div>
        </div>

        <div className="pt-4 animate-fade-in-up stagger-4">
          <button
            type="submit"
            disabled={loading}
            className="group w-full flex items-center justify-center gap-3 bg-ink-900 dark:bg-cream-200 hover:bg-ink-800 dark:hover:bg-cream-300 disabled:bg-ink-400 text-cream-50 dark:text-ink-800 font-medium py-3.5 px-6 text-sm tracking-wide transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-warm focus:ring-offset-2 focus:ring-offset-cream-50 dark:focus:ring-offset-ink-900"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-cream-50/30 border-t-cream-50 rounded-full animate-spin" />
                Signing in
              </span>
            ) : (
              <>
                Sign in
                <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1" />
              </>
            )}
          </button>
        </div>
      </form>

      <p className="mt-10 text-center text-xs text-ink-400 dark:text-ink-400 animate-fade-in-up stagger-5">
        Don&apos;t have an account?{' '}
        <span className="text-ink-500 dark:text-ink-300">Contact an admin</span>
      </p>
    </div>
  )
}
