const TOKEN_KEY = 'code_review_token'
const USER_KEY = 'code_review_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

export function getUser() {
  const data = localStorage.getItem(USER_KEY)
  return data ? JSON.parse(data) : null
}

export function setUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function removeUser() {
  localStorage.removeItem(USER_KEY)
}

export function clearAuth() {
  removeToken()
  removeUser()
}
