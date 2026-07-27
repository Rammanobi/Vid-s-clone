// Tiny typed wrapper around sessionStorage/localStorage.
//
// - sessionStorage: short-lived data that's fine to re-fetch (dashboard/analytics
//   summaries). Survives refresh/navigation within the tab, gone when the tab closes.
//   Always paired with a TTL - it's a perceived-speed optimization, never a source
//   of truth, so callers should still fetch a fresh copy in the background.
// - localStorage: data that should genuinely persist across browser restarts
//   (e.g. the current chat session id).
//
// Both storages don't exist during Next.js SSR, so every access is guarded.

interface CacheEnvelope<T> {
  value: T
  savedAt: number
}

function isStorageAvailable(storage: Storage | undefined): storage is Storage {
  return typeof window !== "undefined" && !!storage
}

function safeGetItem(storage: Storage | undefined, key: string): string | null {
  if (!isStorageAvailable(storage)) return null
  try {
    return storage.getItem(key)
  } catch {
    return null
  }
}

function safeSetItem(storage: Storage | undefined, key: string, value: string): void {
  if (!isStorageAvailable(storage)) return
  try {
    storage.setItem(key, value)
  } catch {
    // Storage full/disabled/private-mode - caching is best-effort, never fatal.
  }
}

function safeRemoveItem(storage: Storage | undefined, key: string): void {
  if (!isStorageAvailable(storage)) return
  try {
    storage.removeItem(key)
  } catch {
    // ignore
  }
}

function getStorage(kind: "session" | "local"): Storage | undefined {
  if (typeof window === "undefined") return undefined
  return kind === "session" ? window.sessionStorage : window.localStorage
}

/** Read a TTL-checked value out of sessionStorage. Returns null if absent, malformed, or expired. */
export function getCached<T>(key: string, ttlMs: number): T | null {
  const raw = safeGetItem(getStorage("session"), key)
  if (!raw) return null
  try {
    const envelope = JSON.parse(raw) as CacheEnvelope<T>
    if (Date.now() - envelope.savedAt > ttlMs) return null
    return envelope.value
  } catch {
    return null
  }
}

/** Write a value to sessionStorage with the current timestamp. */
export function setCached<T>(key: string, value: T): void {
  const envelope: CacheEnvelope<T> = { value, savedAt: Date.now() }
  safeSetItem(getStorage("session"), key, JSON.stringify(envelope))
}

/** Remove a cached sessionStorage entry. */
export function clearCached(key: string): void {
  safeRemoveItem(getStorage("session"), key)
}

/** Read a plain string from localStorage (no TTL - meant to persist across restarts). */
export function getPersistent(key: string): string | null {
  return safeGetItem(getStorage("local"), key)
}

/** Write a plain string to localStorage. */
export function setPersistent(key: string, value: string): void {
  safeSetItem(getStorage("local"), key, value)
}

/** Remove a persistent localStorage entry. */
export function clearPersistent(key: string): void {
  safeRemoveItem(getStorage("local"), key)
}
