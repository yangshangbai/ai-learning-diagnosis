import request from './request'

export const diagnosesAPI = {
  getList: (params) => request.get('/diagnosis', { params }),
  getById: (id) => request.get(`/diagnosis/${id}`),
  update: (id, data) => request.put(`/diagnosis/${id}`, data),
  batchConfirm: (data) => request.post('/diagnosis/batch-confirm', data),
  getBoard: (params) => request.get('/diagnosis/board', { params }),
}
