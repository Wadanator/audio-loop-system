import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { api } from '../services/api.js';

const AUTH_STORAGE_KEY = 'auth_header';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(localStorage.getItem(AUTH_STORAGE_KEY)));
  const [loginError, setLoginError] = useState('');

  const login = useCallback(async (username, password) => {
    try {
      const authHeader = await api.login(username, password);
      localStorage.setItem(AUTH_STORAGE_KEY, authHeader);
      setLoginError('');
      setIsAuthenticated(true);
      return true;
    } catch (error) {
      setLoginError(error?.message || 'Zlé heslo alebo meno');
      setIsAuthenticated(false);
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(AUTH_STORAGE_KEY);
    setIsAuthenticated(false);
    setLoginError('');
  }, []);

  const value = useMemo(() => ({
    isAuthenticated,
    login,
    logout,
    loginError,
  }), [isAuthenticated, login, logout, loginError]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return value;
}
