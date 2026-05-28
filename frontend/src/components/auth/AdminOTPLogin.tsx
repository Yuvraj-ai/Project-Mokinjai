import { useState, FormEvent } from 'react'
import { useAuth } from '../../hooks/useAuth'
import { Shield, KeyRound, AlertCircle, Loader2, CheckCircle2 } from 'lucide-react'

export default function AdminOTPLogin() {
  const { adminOtpLogin } = useAuth()
  const [showOTP, setShowOTP] = useState(false)
  const [otp, setOtp] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)

  const handleRequestOTP = async () => {
    setError(null)
    setLoading(true)
    try {
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
      await adminOtpLogin(otp)
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Invalid OTP. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (!showOTP) {
    return (
      <div className="mt-6 pt-6 border-t border-gray-200">
        <button
          onClick={handleRequestOTP}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 bg-gray-100 hover:bg-gray-200 disabled:bg-gray-50 text-gray-700 font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
        >
          <Shield className="w-4 h-4" />
          Admin Login via OTP
        </button>
      </div>
    )
  }

  return (
    <div className="mt-6 pt-6 border-t border-gray-200">
      <div className="flex items-center gap-2 mb-4 text-sm text-gray-600">
        <KeyRound className="w-4 h-4" />
        <span className="font-medium">Enter 6-digit OTP from Telegram</span>
      </div>

      {sent && (
        <div className="mb-4 flex items-center gap-2 bg-green-50 border border-green-200 text-green-700 rounded-lg px-4 py-2.5 text-sm">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>OTP sent to admin Telegram</span>
        </div>
      )}

      {error && (
        <div className="mb-4 flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-2.5 text-sm">
          <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <input
            type="text"
            value={otp}
            onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
            required
            maxLength={6}
            placeholder="000000"
            className="w-full text-center text-2xl tracking-[1em] font-mono py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors"
            autoComplete="off"
          />
        </div>

        <button
          type="submit"
          disabled={loading || otp.length !== 6}
          className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 flex items-center justify-center gap-2"
        >
          {loading && <Loader2 className="w-4 h-4 animate-spin" />}
          {loading ? 'Verifying...' : 'Verify & Login'}
        </button>

        <button
          type="button"
          onClick={() => { setShowOTP(false); setOtp(''); setError(null); setSent(false) }}
          className="w-full text-gray-500 hover:text-gray-700 text-sm py-1.5 transition-colors"
        >
          Back
        </button>
      </form>
    </div>
  )
}
