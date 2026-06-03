const PARAM = 'c'

export function readConversationIdFromUrl(): string | null {
  if (typeof window === 'undefined') return null
  const value = new URLSearchParams(window.location.search).get(PARAM)
  return value && value.trim() ? value : null
}

export function writeConversationIdToUrl(id: string | null): void {
  if (typeof window === 'undefined') return
  if (readConversationIdFromUrl() === id) return
  const url = new URL(window.location.href)
  if (id === null) url.searchParams.delete(PARAM)
  else url.searchParams.set(PARAM, id)
  const next = url.pathname + (url.search ? url.search : '') + url.hash
  window.history.replaceState({}, '', next)
}
