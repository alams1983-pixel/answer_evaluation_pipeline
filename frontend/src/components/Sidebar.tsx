"use client";

import { useAuth } from '@/lib/auth';
import { useLayout } from '@/components/LayoutContext';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import IconDashboard from '@/components/icons/IconDashboard';
import IconUsers from '@/components/icons/IconUsers';
import IconStudents from '@/components/icons/IconStudents';
import IconClasses from '@/components/icons/IconClasses';
import IconSubjects from '@/components/icons/IconSubjects';
import IconExams from '@/components/icons/IconExams';
import IconSchemas from '@/components/icons/IconSchemas';
import IconPassword from '@/components/icons/IconPassword';
import IconProfile from '@/components/icons/IconProfile';

const sections = [
  {
    label: 'Overview',
    items: [
      { href: '/', label: 'Dashboard', roles: ['admin', 'teacher', 'student'], icon: IconDashboard },
    ],
  },
  {
    label: 'Manage',
    items: [
      { href: '/users', label: 'Users', roles: ['admin', 'teacher'], icon: IconUsers },
      { href: '/students', label: 'Students', roles: ['admin', 'teacher'], icon: IconStudents },
      { href: '/classes', label: 'Classes', roles: ['admin', 'teacher'], icon: IconClasses },
      { href: '/subjects', label: 'Subjects', roles: ['admin', 'teacher'], icon: IconSubjects },
    ],
  },
  {
    label: 'Assessments',
    items: [
      { href: '/exams', label: 'Exams', roles: ['admin', 'teacher'], icon: IconExams },
      { href: '/result-schemas', label: 'Result Schemas', roles: ['admin', 'teacher'], icon: IconSchemas },
    ],
  },
  {
    label: 'Account',
    items: [
      { href: '/profile', label: 'Profile', roles: ['admin', 'teacher', 'student'], icon: IconProfile },
      { href: '/change-password', label: 'Change Password', roles: ['admin', 'teacher', 'student'], icon: IconPassword },
    ],
  },
];

export default function Sidebar() {
  const { user } = useAuth();
  const { sidebarOpen, closeSidebar } = useLayout();
  const pathname = usePathname();

  if (!user) return null;

  return (
    <>
      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={closeSidebar}
          aria-hidden="true"
        />
      )}
      <nav className={`sidebar ${sidebarOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-logo">
          <svg className="sidebar-logo-icon" xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
          </svg>
          <span className="sidebar-logo-text">AI PDF Processing</span>
        </div>
        <div className="sidebar-content">
          {sections.map((section) => {
            const visibleItems = section.items.filter(item => item.roles.includes(user.role));
            if (visibleItems.length === 0) return null;
            return (
              <div key={section.label} className="sidebar-section">
                <div className="sidebar-section-label">{section.label}</div>
                <ul className="sidebar-nav">
                  {visibleItems.map(item => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                          onClick={() => {
                            if (window.innerWidth < 1024) closeSidebar();
                          }}
                        >
                          <Icon />
                          <span>{item.label}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      </nav>
    </>
  );
}
