import request from './request'

export const auditAPI = {
  getList: (params) => request.get('/audit', { params }),
}
