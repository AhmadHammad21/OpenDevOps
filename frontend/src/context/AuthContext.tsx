import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

interface AuthUser {
  id: string | null;
  role: string;
  name: string;
  auth_enabled: boolean;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (email: string, name: string, password: string) => Promise<void>;
  isAdmin: boolean;
  isAuthenticated: boolean;
  authRequired: boolean;
  loading: boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('auth-token'));
  const [user, setUser]   = useState<AuthUser | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchMe = useCallback(async (t: string | null): Promise<boolean> => {
    try {
      const res = await fetch('/auth/me', {
        headers: t ? { Authorization: `Bearer ${t}` } : {},
      });
      if (res.ok) {
        setUser(await res.json() as AuthUser);
        return true;
      }
    } catch { /* ignore */ }
    return false;
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/auth/status');
        if (res.ok) {
          const { required } = await res.json() as { required: boolean };
          setAuthRequired(required);
          if (!required) {
            setUser({ id: null, role: 'admin', auth_enabled: false });
            setLoading(false);
            return;
          }
        }
      } catch { /* auth/status unavailable */ }

      if (token) {
        const ok = await fetchMe(token);
        if (!ok) {
          localStorage.removeItem('auth-token');
          setToken(null);
        }
      }
      setLoading(false);
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = async (email: string, password: string) => {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json() as { detail?: string };
      throw new Error(err.detail ?? 'Login failed');
    }
    const { access_token } = await res.json() as { access_token: string };
    localStorage.setItem('auth-token', access_token);
    setToken(access_token);
    await fetchMe(access_token);
  };

  const register = async (email: string, name: string, password: string) => {
    const res = await fetch('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, name, password }),
    });
    if (!res.ok) {
      const err = await res.json() as { detail?: string };
      throw new Error(err.detail ?? 'Registration failed');
    }
    const { access_token } = await res.json() as { access_token: string };
    localStorage.setItem('auth-token', access_token);
    setToken(access_token);
    await fetchMe(access_token);
  };

  const logout = () => {
    localStorage.removeItem('auth-token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user, token, login, logout, register,
      isAdmin: user?.role === 'admin',
      isAuthenticated: !!user,
      authRequired,
      loading,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
