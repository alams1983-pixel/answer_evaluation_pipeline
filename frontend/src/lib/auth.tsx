"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'admin' | 'teacher' | 'student';
  class_id?: string | null;
  roll_no?: string | null;
  is_active: boolean;
  created_at: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  changePassword: (current: string, newPass: string) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

function setTokenCookie(token: string | null) {
  if (typeof document !== 'undefined') {
    if (token) {
      document.cookie = `auth_token=${token}; path=/; max-age=86400; SameSite=Lax`;
    } else {
      document.cookie = 'auth_token=; path=/; max-age=0; SameSite=Lax';
    }
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const storedToken = localStorage.getItem('auth_token');
    if (storedToken) {
      setToken(storedToken);
      setTokenCookie(storedToken);
      fetchMe(storedToken);
    } else {
      setLoading(false);
    }
  }, []);

  const fetchMe = async (authToken: string) => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    try {
      const res = await fetch(`${baseUrl}/auth/me/`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error('Unauthorized');
      const data = await res.json();
      setUser(data);
    } catch (err) {
      localStorage.removeItem('auth_token');
      setToken(null);
      setTokenCookie(null);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email: string, password: string) => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const res = await fetch(`${baseUrl}/auth/login/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || err.message || 'Login failed');
    }
    const data = await res.json();
    localStorage.setItem('auth_token', data.access_token);
    setToken(data.access_token);
    setTokenCookie(data.access_token);
    await fetchMe(data.access_token);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
    setTokenCookie(null);
  };

  const changePassword = async (current: string, newPass: string) => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
    const token = localStorage.getItem('auth_token');
    const res = await fetch(`${baseUrl}/auth/change-password/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ current_password: current, new_password: newPass }),
    });
    if (!res.ok) throw new Error('Password change failed');
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
