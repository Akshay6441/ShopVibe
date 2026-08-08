import api from './client';

export const getTickets = () => api.get('/api/tickets');
export const updateTicketStatus = (id, status) =>
  api.put(`/api/tickets/${id}`, { status });
