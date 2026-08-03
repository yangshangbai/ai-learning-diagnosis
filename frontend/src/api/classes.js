import request from './request'

export const classesAPI = {
  getList: (params) => request.get('/classes', { params }),
  create: (data) => request.post('/classes', data),
  update: (id, data) => request.put(`/classes/${id}`, data),
  remove: (id) => request.delete(`/classes/${id}`),

  // Grade endpoints
  getGrades: () => request.get('/classes/grades'),
  createGrade: (data) => request.post('/classes/grades', data),
  updateGrade: (id, data) => request.put(`/classes/grades/${id}`, data),
  removeGrade: (id) => request.delete(`/classes/grades/${id}`),
}
