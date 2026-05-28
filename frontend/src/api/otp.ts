import apiClient from './client'

interface OTPSendResponse {
  session_token: string
  expires_in: number
  message: string
}

interface OTPValidateResponse {
  access_token: string
  refresh_token: string
  message: string
}

export async function sendAdminOTP(): Promise<OTPSendResponse> {
  const response = await apiClient.post<OTPSendResponse>('/api/auth/admin/otp/send')
  return response.data
}

export async function validateAdminOTP(sessionToken: string, code: string): Promise<OTPValidateResponse> {
  const response = await apiClient.post<OTPValidateResponse>('/api/auth/admin/otp/validate', {
    session_token: sessionToken,
    code,
  })
  return response.data
}
