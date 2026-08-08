import api from './client';

export const createOrder = (data) => api.post('/api/orders', data);
export const getMyOrders = () => api.get('/api/orders');
export const getOrder = (id) => api.get(`/api/orders/${id}`);

// Admin
export const adminGetOrders = () => api.get('/api/admin/orders');
export const adminUpdateOrderStatus = (id, status) =>
  api.put(`/api/admin/orders/${id}/status`, { status });
export const adminGetStats = () => api.get('/api/admin/stats');
export const adminSyncOrderToSalesforce = (id) =>
  api.post(`/api/admin/orders/${id}/sync-salesforce`);
