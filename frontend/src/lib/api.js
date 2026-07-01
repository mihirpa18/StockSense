import axios from 'axios'
import { supabase } from './supabase'

const API = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
  timeout: 120000 // 2 min timeout for auto-research & large uploads
})

// Every request carries the Supabase access token so the backend's
// get_current_user_id dependency can verify identity. The backend no
// longer accepts user_id as a Form/Body/Query field.
API.interceptors.request.use(async (config) => {
  const { data: { session } } = await supabase.auth.getSession()
  if (session?.access_token) {
    config.headers.Authorization = `Bearer ${session.access_token}`
  }
  return config
})

// ─── Upload ──────────────────────────────────────────────────────
export const uploadDocument = (formData) =>
  API.post('/api/upload/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })

// ─── Chat ────────────────────────────────────────────────────────
export const sendChat = (payload) =>
  API.post('/api/chat/', payload)

export const getChatSessions = (companyId) =>
  API.get(`/api/chat/${companyId}/sessions`)

export const getChatHistory = (sessionId) =>
  API.get(`/api/chat/session/${sessionId}`)

// ─── Thesis ──────────────────────────────────────────────────────
export const saveThesis = (thesis) =>
  API.post('/api/thesis/', thesis)

export const getThesis = (companyId) =>
  API.get(`/api/thesis/${companyId}`)

export const autoDraftThesis = (companyId, documentId) =>
  API.post(`/api/thesis/${companyId}/auto-draft?document_id=${documentId}`)

export const reviewThesis = (thesisId, documentId, mode = 'document', searchQuery = '') => {
  let url = `/api/thesis/${thesisId}/review?mode=${mode}`
  if (documentId) url += `&document_id=${documentId}`
  if (searchQuery) url += `&search_query=${encodeURIComponent(searchQuery)}`
  return API.post(url)
}

// ─── Journal ─────────────────────────────────────────────────────
export const saveJournalEntry = (entry) =>
  API.post('/api/journal/', entry)

export const getJournalEntries = () =>
  API.get('/api/journal/')

// ─── Companies ───────────────────────────────────────────────────
export const searchCompanies = (query) =>
  API.get(`/api/companies/search?q=${encodeURIComponent(query)}`)

export const createCompany = (company) =>
  API.post('/api/companies/', company)

export const getCompany = (companyId) =>
  API.get(`/api/companies/${companyId}`)

export const getCompanyFundamentals = (companyId) =>
  API.get(`/api/companies/${companyId}/fundamentals`)

export const getCompanyDocuments = (companyId) =>
  API.get(`/api/companies/${companyId}/documents`)

export const triggerAutoResearch = (companyId, payload = {}) =>
  API.post(`/api/companies/${companyId}/auto-research`, payload)

// ─── Watchlist ───────────────────────────────────────────────────
export const getWatchlist = () =>
  API.get('/api/companies/watchlist')

export const addToWatchlist = (companyId) =>
  API.post(`/api/companies/watchlist/${companyId}`)

export const removeFromWatchlist = (companyId) =>
  API.delete(`/api/companies/watchlist/${companyId}`)

// ─── Price / Fundamentals Refresh ────────────────────────────────
export const refreshPrice = (companyId) =>
  API.post(`/api/companies/${companyId}/refresh-price`)

export const refreshPricesBulk = (companyIds) =>
  API.post('/api/companies/refresh-prices', { company_ids: companyIds })

export const refreshFundamentals = (companyId) =>
  API.post(`/api/companies/${companyId}/refresh-fundamentals`)

// ─── Notes ───────────────────────────────────────────────────────
export const getNotes = (companyId) =>
  API.get(`/api/notes/${companyId}`)

export const saveNote = (note) =>
  API.post('/api/notes/', note)

export default API
