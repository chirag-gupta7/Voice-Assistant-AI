import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:5000',
  withCredentials: true
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const authService = {
  login: (email, password) => api.post('/api/auth/login', { email, password }).then((res) => res.data),
  register: (name, email, password) => api.post('/api/auth/register', { name, email, password }).then((res) => res.data),
  googleLogin: (token) => api.post('/api/auth/google', { token }).then((res) => res.data),
  getCurrentUser: () => api.get('/api/auth/me').then((res) => res.data)
};

export const meetingService = {
  getMeetings: () => api.get('/api/meetings').then((res) => res.data),
  createMeeting: (payload) => api.post('/api/meetings', payload).then((res) => res.data),
  processVoiceCommand: (transcript) => api.post('/api/voice/process', { transcript }).then((res) => res.data)
};

export const calendarService = {
  getEvents: () => api.get('/api/calendar/events').then((res) => res.data),
  sync: () => api.post('/api/calendar/sync').then((res) => res.data)
};

export default api;
