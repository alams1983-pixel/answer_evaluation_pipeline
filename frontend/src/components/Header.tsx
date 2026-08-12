"use client";

import { useAuth } from '@/lib/auth';
import { useLayout, useTheme } from '@/components/LayoutContext';
import { useRouter } from 'next/navigation';
import IconMenu from '@/components/icons/IconMenu';
import IconSun from '@/components/icons/IconSun';
import IconMoon from '@/components/icons/IconMoon';
import IconLogout from '@/components/icons/IconLogout';

export default function Header() {
  const { user, logout } = useAuth();
  const { toggleSidebar } = useLayout();
  const { theme, toggleTheme } = useTheme();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  if (!user) return null;

  const initials = user.full_name
    .split(' ')
    .map(n => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="app-header">
      <div className="header-left">
        <button
          className="sidebar-toggle-btn"
          onClick={toggleSidebar}
          aria-label="Toggle sidebar"
        >
          <IconMenu />
        </button>
        <span className="logo">AI PDF Processing</span>
      </div>

      <div className="header-right">
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
        >
          {theme === 'light' ? <IconMoon /> : <IconSun />}
        </button>
        <div className="user-avatar" title={user.full_name}>
          {initials}
        </div>
        <span className="user-name">
          {user.full_name}
        </span>
        <button
          className="btn-icon"
          onClick={handleLogout}
          aria-label="Logout"
          title="Logout"
        >
          <IconLogout />
        </button>
      </div>
    </header>
  );
}
