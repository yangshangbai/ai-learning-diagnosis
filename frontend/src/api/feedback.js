import request from './request'

export const feedbackAPI = {
  list: (params) => request.get('/feedback', { params }),
  getById: (id) => request.get(`/feedback/${id}`),
  create: (data) => request.post('/feedback', data),
  update: (id, data) => request.put(`/feedback/${id}`, data),
  delete: (id) => request.delete(`/feedback/${id}`),
  accept: (id) => request.put(`/feedback/${id}/accept`),
  complete: (id) => request.put(`/feedback/${id}/complete`),
  uploadImage: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request.post('/feedback/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}
