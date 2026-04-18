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

/** 删除单条评审记录 */
export function deleteReview(id) {
  return request.delete(`/reviews/${id}`)
}

/** 批量删除评审记录 */
export function batchDeleteReviews(taskIds) {
  return request.post('/reviews/batch-delete', { task_ids: taskIds })
}

/** 按日期范围删除评审记录 */
export function deleteReviewsByDate(startDate, endDate, projectId) {
  return request.post('/reviews/delete-by-date', {
    start_date: startDate,
    end_date: endDate,
    project_id: projectId
  })
}

/** 手动触发评审 */
export function createManualReview(data) {
  return request.post('/reviews/manual', data)
}

/** 清空所有评审记录 */
export function clearAllReviews() {
  return request.delete('/reviews/all')
}
