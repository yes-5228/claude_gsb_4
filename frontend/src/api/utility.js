import { http } from './client.js';

const RESOURCE = '/utility-records';

export const utilityApi = {
  list: (params) => http.get(RESOURCE, params),
  detail: (id) => http.get(`${RESOURCE}/${id}`),
  create: (payload) => http.post(RESOURCE, payload),
  update: (id, payload) => http.patch(`${RESOURCE}/${id}`, payload),
  remove: (id) => http.delete(`${RESOURCE}/${id}`),
  baseline: (restroomId, year, month) =>
    http.get(`${RESOURCE}/baseline`, {
      restroom_id: restroomId,
      period_year: year,
      period_month: month,
    }),
};
