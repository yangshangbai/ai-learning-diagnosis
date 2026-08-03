import request from './request'

export const dashboardAPI = {
  getStats: () => request.get('/admin/stats'),
}
