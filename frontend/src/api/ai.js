import request from './request'

export const aiAPI = {
  suggest: (data) => request.post('/ai/suggest', data),
}
