import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { getToken } from '@/services/api'
import {
  fetchMe,
  initialsFor,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  type AuthUser,
} from '@/services/auth'

interface AuthContextValue {
  user: AuthUser | null
  initials: string
  isAuthenticated: boolean
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (payload: {
    email: string
    password: string
    full_name?: string
    role?: string
  }) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function hydrate() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const me = await fetchMe()
        if (!cancelled) setUser(me)
      } catch {
        if (!cancelled) {
          queryClient.clear()
          setUser(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    hydrate()
    return () => {
      cancelled = true
    }
  }, [queryClient])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      initials: user ? initialsFor(user) : '',
      isAuthenticated: Boolean(user),
      loading,
      async login(email, password) {
        const nextUser = await loginRequest(email, password)
        queryClient.clear()
        setUser(nextUser)
      },
      async register(payload) {
        const nextUser = await registerRequest(payload)
        queryClient.clear()
        setUser(nextUser)
      },
      logout() {
        logoutRequest()
        queryClient.clear()
        setUser(null)
      },
    }),
    [user, loading, queryClient],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
