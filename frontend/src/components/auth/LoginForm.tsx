import { useState, FormEvent } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { Mail, Lock, AlertCircle, ArrowRight } from 'lucide-react'
import { Label } from '../ui/Field'
import Button from '../ui/Button'
import { Callout } from '../ui/Feedback'

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

  const inputClass =
    'w-full rounded-lg border border-line bg-surface h-10 px-9 pr-3 py-2 text-sm text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring transition-colors'

  return (
    <div className="w-full">
      <div className="mb-7">
        <h2 className="text-xl font-semibold text-ink tracking-tight animate-fade-in-up">
          Welcome back
        </h2>
        <p className="mt-1 text-sm text-ink-muted animate-fade-in-up stagger-1">
          Sign in to continue to your workspace
        </p>
      </div>

      {error && (
        <div className="mb-6 animate-fade-in">
          <Callout tone="danger">
            <span className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
              {error}
            </span>
          </Callout>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="animate-fade-in-up stagger-2">
          <Label htmlFor="email" required>
            Email
          </Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle pointer-events-none" aria-hidden />
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className={inputClass}
            />
          </div>
        </div>

        <div className="animate-fade-in-up stagger-3">
          <Label htmlFor="password" required>
            Password
          </Label>
          <div className="relative">
            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ink-subtle pointer-events-none" aria-hidden />
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
              className={inputClass}
            />
          </div>
        </div>

        <div className="pt-2 animate-fade-in-up stagger-4">
          <Button type="submit" loading={loading} className="group w-full h-10 px-4 py-2">
            {loading ? (
              'Signing in'
            ) : (
              <>
                Sign in
                <ArrowRight className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-0.5" aria-hidden />
              </>
            )}
          </Button>
        </div>
      </form>

      <p className="mt-8 text-center text-xs text-ink-subtle animate-fade-in-up stagger-5">
        Don&apos;t have an account?{' '}
        <span className="text-ink-muted">Contact an admin</span>
      </p>
    </div>
  )
}
