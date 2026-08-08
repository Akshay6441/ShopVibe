import api from './client';

export const runAgent = (instruction) => api.post('/api/ai/agent', { instruction });
