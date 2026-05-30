import { useState, FormEvent } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { sendAdminOTP } from '../../api/otp'
import { Shield, KeyRound, AlertCircle, CheckCircle2 } from 'lucide-react'

export default function AdminOTPLogin() {
  const { adminOtpLogin } = useAuth()
  const [showOTP, setShowOTP] = useState(false)
  const [sessionToken, setSessionToken] = useState('')
  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const handleRequestOTP = async () => {
    setError(null)
    setLoading(true)
    try {
      const res = await sendAdminOTP()
      setSessionToken(res.session_token)
      setShowOTP(true)
      setSent(true)
    } catch {
      setError('Failed to request OTP')
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await adminOtpLogin(sessionToken, otp)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid OTP. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (!showOTP) {
    return (
      <div className="mt-8 pt-8 border-t border-ink-200/50 dark:border-ink-700/50 animate-fade-in-up stagger-6">
        <button
          onClick={handleRequestOTP}
          disabled={loading}
          className="group w-full flex items-center justify-center gap-2.5 border border-ink-200 dark:border-ink-600 hover:border-ink-400 dark:hover:border-ink-500 disabled:border-ink-100 text-ink-600 dark:text-ink-300 hover:text-ink-900 dark:hover:text-cream-100 font-medium py-3 px-4 text-sm tracking-wide transition-all duration-300"
        >
          <Shield className="w-4 h-4 text-accent-warm" />
          Admin Login via OTP
        </button>
      </div>
    )
  }

  return (
    <div className="mt-8 pt-8 border-t border-ink-200/50 dark:border-ink-700/50 animate-fade-in">
      <div className="flex items-center gap-2.5 mb-6">
        <KeyRound className="w-4 h-4 text-accent-warm" />
        <span className="text-xs font-medium text-ink-500 dark:text-ink-300 tracking-widest uppercase">
          Telegram OTP
        </span>
      </div>

      {sent && (
        <div className="mb-6 flex items-center gap-2.5 bg-status-success/5 border border-status-success/20 text-status-success rounded-sm px-4 py-3 text-sm animate-fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>OTP sent to admin Telegram</span>
        </div>
      )}

      {error && (
        <div className="mb-6 flex items-start gap-2.5 bg-status-error/5 border border-status-error/20 text-status-error rounded-sm px-4 py-3 text-sm animate-fade-in">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="animate-fade-in-up">
          <input
            type="text"
            value={otp}
            onChange={(e) =>
              setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))
            }
            required
            maxLength={6}
            placeholder="000000"
            className="w-full text-center text-2xl font-mono tracking-[0.5em] py-4 bg-transparent border-b border-ink-200 dark:border-ink-600 text-ink-900 dark:text-cream-100 placeholder:text-ink-400 dark:placeholder:text-ink-500 focus:outline-none focus:border-accent-warm transition-colors duration-300"
            autoComplete="off"
          />
        </div>

        <div className="animate-fade-in-up stagger-1">
          <button
            type="submit"
            disabled={loading || otp.length !== 6}
            className="group w-full flex items-center justify-center gap-3 bg-ink-900 dark:bg-cream-200 hover:bg-ink-800 dark:hover:bg-cream-300 disabled:bg-ink-400 text-cream-50 dark:text-ink-800 font-medium py-3.5 px-6 text-sm tracking-wide transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-warm focus:ring-offset-2 focus:ring-offset-cream-50 dark:focus:ring-offset-ink-900"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-4 h-4 border-2 border-cream-50/30 border-t-cream-50 rounded-full animate-spin" />
                Verifying
              </span>
            ) : (
              'Verify & Login'
            )}
          </button>
        </div>

        <button
          type="button"
          onClick={() => {
            setShowOTP(false)
            setOtp('')
            setError(null)
            setSent(false)
          }}
          className="w-full text-ink-400 dark:text-ink-400 hover:text-ink-700 dark:hover:text-cream-200 text-xs tracking-widest uppercase py-2 transition-colors duration-300"
        >
          Back to email
        </button>
      </form>
    </div>
  )
}
