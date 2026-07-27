"use client"

import { createContext, useContext, useState, useEffect, type ReactNode } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"

interface AuthContextType {
  token: string | null
  user: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  isLoading: boolean
}

const AuthContext = createContext<AuthContextType>({
  token: null,
  user: null,
  login: async () => {},
  logout: () => {},
  isLoading: true,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const stored = localStorage.getItem("auth_token")
    const storedUser = localStorage.getItem("auth_user")
    if (stored && storedUser) {
      setToken(stored)
      setUser(storedUser)
      setIsLoading(false)
      return
    }

    // No login page exists in this app - it's a single-admin local tool.
    // Silently authenticate as the one configured account instead of
    // showing a sign-in step for a "user" that isn't really a separate
    // identity here.
    const autoUsername = process.env.NEXT_PUBLIC_ADMIN_USERNAME
    const autoPassword = process.env.NEXT_PUBLIC_ADMIN_PASSWORD
    if (autoUsername && autoPassword) {
      api.auth
        .login(autoUsername, autoPassword)
        .then((result) => {
          localStorage.setItem("auth_token", result.access_token)
          localStorage.setItem("auth_user", autoUsername)
          setToken(result.access_token)
          setUser(autoUsername)
        })
        .catch(() => {
          // Backend not reachable yet or credentials misconfigured - pages
          // that need a token will show their own "sign in" error; nothing
          // to recover here automatically.
        })
        .finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [])

  const login = async (username: string, password: string) => {
    const result = await api.auth.login(username, password)
    localStorage.setItem("auth_token", result.access_token)
    localStorage.setItem("auth_user", username)
    setToken(result.access_token)
    setUser(username)
  }

  const logout = () => {
    localStorage.removeItem("auth_token")
    localStorage.removeItem("auth_user")
    setToken(null)
    setUser(null)
    router.push("/dashboard")
  }

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within AuthProvider")
  return context
}
