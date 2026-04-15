import request from './index'

/** 获取评审列表 */
export function getReviews(params) {
  return request.get('/reviews', { params })
}

/** 获取评审详情 */
export function getReview(id) {
  return request.get(`/reviews/${id}`)
}

/** 获取评审评论 */
export function getReviewComments(id) {
  return request.get(`/reviews/${id}/comments`)
}
