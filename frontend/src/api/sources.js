import request from './request'

export const sourcesAPI = {
  getStatus: () => request.get('/sources/status'),
  updatePolicy: (data) => request.put('/sources/policy', data),
  sync: () => request.post('/sources/sync'),
  getOperations: (params) => request.get('/sources/operations', { params }),
  getCandidates: (params) => request.get('/sources/candidates', { params }),
  acceptCandidate: (id) => request.post(`/sources/candidates/${id}/accept`),
  rejectCandidate: (id) => request.post(`/sources/candidates/${id}/reject`),
}
