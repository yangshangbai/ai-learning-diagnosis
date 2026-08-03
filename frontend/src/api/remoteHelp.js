import request from './request'

export const remoteHelpAPI = {
  execute: (data) => request.post('/admin/remote-help', data),
  getHistory: () => request.get('/admin/remote-help/history'),
}
