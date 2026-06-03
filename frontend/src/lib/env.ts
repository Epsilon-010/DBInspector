function sameOriginHttp(): string {
  if (typeof window === 'undefined') return 'http://localhost:8000'
  return window.location.origin
}

function sameOriginWs(): string {
  if (typeof window === 'undefined') return 'ws://localhost:8000'
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}`
}

const apiUrl = import.meta.env.VITE_API_URL?.trim() || sameOriginHttp()
const wsUrl = import.meta.env.VITE_WS_URL?.trim() || sameOriginWs()

export const env = {
  apiBaseUrl: apiUrl.replace(/\/$/, ''),
  wsUrl: `${wsUrl.replace(/\/$/, '')}/graphql`,
  graphqlUrl: `${apiUrl.replace(/\/$/, '')}/graphql`,
} as const
