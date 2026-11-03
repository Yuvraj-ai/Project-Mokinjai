import { useState, FormEvent } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { sendAdminOTP } from '../../api/otp'
import { Shield, KeyRound, AlertCircle, CheckCircle2 } from 'lucide-react'
import Button from '../ui/Button'
import { Callout } from '../ui/Feedback'

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
      <div className="mt-7 pt-7 border-t border-line animate-fade-in-up stagger-6">
        {error && (
          <div className="mb-3">
            <Callout tone="danger">{error}</Callout>
          </div>
        )}
        <Button
          variant="secondary"
          disabled={loading}
          onClick={() => void handleRequestOTP()}
          className="w-full h-10 py-2"
        >
          <Shield className="w-4 h-4" aria-hidden />
          Admin Login via OTP
        </Button>
      </div>
    )
  }

  return (
    <div className="mt-7 pt-7 border-t border-line animate-fade-in">
      <div className="flex items-center gap-2.5 mb-5">
        <KeyRound className="w-4 h-4 text-ink-muted" aria-hidden />
        <span className="text-[13px] font-medium text-ink">Telegram OTP</span>
      </div>

      {sent && (
        <div className="mb-5">
          <Callout tone="success">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" aria-hidden />
              OTP sent to admin Telegram
            </span>
          </Callout>
        </div>
      )}

      {error && (
        <div className="mb-5">
          <Callout tone="danger">
            <span className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden />
              {error}
            </span>
          </Callout>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
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
            className="w-full text-center text-2xl font-mono tracking-[0.5em] h-14 rounded-lg border border-line bg-surface text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-2 focus:ring-ring transition-colors"
            autoComplete="off"
          />
        </div>

        <div className="animate-fade-in-up stagger-1">
          <Button type="submit" loading={loading} disabled={otp.length !== 6} className="w-full h-10">
            {loading ? 'Verifying' : 'Verify & Login'}
          </Button>
        </div>

        <button
          type="button"
          onClick={() => {
            setShowOTP(false)
            setOtp('')
            setError(null)
            setSent(false)
          }}
          className="w-full text-ink-subtle hover:text-ink text-xs py-1 transition-colors duration-150"
        >
          Back to email
        </button>
      </form>
    </div>
  )
}
