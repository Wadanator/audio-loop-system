import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const AUTH_STORAGE_KEY = 'auth_header';
const VALID_USERNAME = 'admin';
const VALID_PASSWORD = 'admin12321';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(localStorage.getItem(AUTH_STORAGE_KEY)));
  const [loginError, setLoginError] = useState('');

  const login = useCallback(async (username, password) => {
    const normalizedUsername = username.trim();
    if (normalizedUsername === VALID_USERNAME && password === VALID_PASSWORD) {
      localStorage.setItem(AUTH_STORAGE_KEY, `Basic ${btoa(`${normalizedUsername}:${password}`)}`);
      setLoginError('');
      setIsAuthenticated(true);
      return true;
    }

    setLoginError('Zlé heslo alebo meno');
    return false;
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