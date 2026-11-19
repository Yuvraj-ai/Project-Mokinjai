// Loaded on demand: a user who never imports from Drive downloads none of Google's
// scripts. The token is returned alongside the picked ids and never stored.

export interface PickedFile {
  id: string
  name: string
  mimeType: string
  sizeBytes?: number
}

export interface GooglePickResult {
  files: PickedFile[]
  accessToken: string
}

const DRIVE_FILE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
const API_SCRIPT = 'https://apis.google.com/js/api.js'
const GIS_SCRIPT = 'https://accounts.google.com/gsi/client'

declare const gapi: {
  load(api: string, options: { callback: () => void; onerror: () => void }): void
}

type TokenResponse = { access_token?: string; error?: string }
type TokenClient = { requestAccessToken: (options?: { prompt?: string }) => void }
type Oauth2 = {
  initTokenClient: (config: {
    client_id: string
    scope: string
    callback: (response: TokenResponse) => void
  }) => TokenClient
}

let scripts: Promise<void> | null = null
let pickerApi: Promise<void> | null = null

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = src
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Could not load ${src}`))
    document.head.appendChild(script)
  })
}

function loadGoogle(): Promise<void> {
  scripts ??= Promise.all([loadScript(API_SCRIPT), loadScript(GIS_SCRIPT)]).then(() => {})
  return scripts
}

function loadPicker(): Promise<void> {
  pickerApi ??= new Promise((resolve, reject) => {
    gapi.load('picker', { callback: () => resolve(), onerror: () => reject(new Error('Picker failed to load')) })
  })
  return pickerApi
}

function requestAccessToken(clientId: string): Promise<string> {
  const oauth2 = (
    window as unknown as { google: { accounts: { oauth2: Oauth2 } } }
  ).google.accounts.oauth2
  return new Promise((resolve, reject) => {
    const client = oauth2.initTokenClient({
      client_id: clientId,
      scope: DRIVE_FILE_SCOPE,
      callback: (response) => {
        if (response.error || !response.access_token) {
          reject(new Error(response.error ?? 'Google did not return an access token'))
        } else {
          resolve(response.access_token)
        }
      },
    })
    client.requestAccessToken({ prompt: '' })
  })
}

export async function pickGoogleFiles(): Promise<GooglePickResult> {
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID
  const apiKey = import.meta.env.VITE_GOOGLE_PICKER_API_KEY
  const appId = import.meta.env.VITE_GOOGLE_PROJECT_NUMBER
  if (!clientId || !apiKey || !appId) {
    throw new Error('Google Drive import is not configured for this build')
  }

  await loadGoogle()
  await loadPicker()
  const accessToken = await requestAccessToken(clientId)

  return new Promise((resolve, reject) => {
    const picker = new google.picker.PickerBuilder()
      // LIST: thumbnails are not granted by `drive.file`.
      .addView(new google.picker.DocsView().setMode(google.picker.DocsViewMode.LIST))
      .setOAuthToken(accessToken)
      .setDeveloperKey(apiKey)
      // Required for drive.file: without the Cloud project number the list is empty.
      .setAppId(appId)
      .setCallback((data: google.picker.ResponseObject) => {
        const action = data[google.picker.Response.ACTION]
        if (action === google.picker.Action.PICKED) {
          const documents = data[google.picker.Response.DOCUMENTS] ?? []
          resolve({
            accessToken,
            files: documents.map((document) => ({
              id: document[google.picker.Document.ID] ?? '',
              name: document[google.picker.Document.NAME] ?? '',
              mimeType: document[google.picker.Document.MIME_TYPE] ?? '',
              sizeBytes: document.sizeBytes,
            })),
          })
        } else if (action === google.picker.Action.CANCEL) {
          resolve({ files: [], accessToken })
        } else if (action === google.picker.Action.ERROR) {
          reject(new Error('Google Picker reported an error'))
        }
        // Other actions (for example LOADED) are not a result: keep waiting.
      })
      .build()
    picker.setVisible(true)
  })
}
