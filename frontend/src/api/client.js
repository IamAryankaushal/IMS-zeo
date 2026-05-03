import axios from 'axios'

const BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: BASE, timeout: 10000 })

export const fetchWorkItems = (params = {}) =>
  api.get('/workitems', { params }).then(r => r.data)

export const fetchWorkItem = (id) =>
  api.get(`/workitems/${id}`).then(r => r.data)

export const fetchWorkItemSignals = (id, limit = 50) =>
  api.get(`/workitems/${id}/signals`, { params: { limit } }).then(r => r.data)

export const transitionWorkItem = (id, status) =>
  api.patch(`/workitems/${id}/transition`, { status }).then(r => r.data)

export const submitRCA = (workItemId, data) =>
  api.post(`/rca/${workItemId}`, data).then(r => r.data)

export const fetchRCA = (workItemId) =>
  api.get(`/rca/${workItemId}`).then(r => r.data)

export const fetchHealth = () =>
  api.get('/health').then(r => r.data)

export const ingestSignal = (payload) =>
  api.post('/signals/ingest', payload).then(r => r.data)
