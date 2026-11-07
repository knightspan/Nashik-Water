import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { api, getTokens, onTokensChange, setTokens } from './api';
import type { User } from './types';

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(Boolean(getTokens()));

  const loadUser = useCallback(async () => {
    if (!getTokens()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadUser();
    return onTokensChange(() => {
      if (!getTokens()) setUser(null);
    });
  }, [loadUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      setTokens(await api.login(email, password));
      await loadUser();
    },
    [loadUser],
  );

  const logout = useCallback(() => setTokens(null), []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth outside AuthProvider');
  return ctx;
}
