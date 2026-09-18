import { http } from './client.js';

const RESOURCE = '/utilities';

export const utilityApi = {
  list: (params) => http.get(RESOURCE, params),
  summary: (params) => http.get(`${RESOURCE}/summary`, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
};
