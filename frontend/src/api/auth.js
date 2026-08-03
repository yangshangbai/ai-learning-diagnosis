import request from './request'

export const authAPI = {
  login: (phone, password) => request.post('/auth/login', { phone, password }),
  logout: () => request.post('/auth/logout'),
  getMe: () => request.get('/auth/me'),
}
