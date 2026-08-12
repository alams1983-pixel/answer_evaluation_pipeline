'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import IconExams from '@/components/icons/IconExams';
import IconStudents from '@/components/icons/IconStudents';
import IconUsers from '@/components/icons/IconUsers';
import IconClasses from '@/components/icons/IconClasses';
import IconSubjects from '@/components/icons/IconSubjects';
import IconSchemas from '@/components/icons/IconSchemas';

interface DashboardStats {
  total_exams?: number;
  total_students?: number;
  pending_sheets?: number;
  graded_sheets?: number;
  active_batches?: number;
  total_gradings?: number;
  pending_results?: number;
  published_results?: number;
}

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    if (!authLoading) {
      setLoading(false);
    }
  }, [authLoading]);

  useEffect(() => {
    if (!authLoading && user) {
      setStatsLoading(true);
      apiGet<DashboardStats>('/dashboard/stats')
        .then(setStats)
        .catch(() => {})
        .finally(() => setStatsLoading(false));
    }
  }, [authLoading, user]);

  if (loading) {
    return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Loading...</div>;
  }

  if (!user) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3rem' }}>
        <section className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <h1 className="text-3xl" style={{ marginBottom: '1rem', fontWeight: 700 }}>
            Welcome to <span style={{ color: 'var(--accent-primary)' }}>AI PDF Processing</span>
          </h1>
          <p className="text-md" style={{ color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto 2rem' }}>
            Answer sheet management and AI grading system. Please sign in to continue.
          </p>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <Link href="/login" className="btn btn-primary">
              Sign In
            </Link>
          </div>
        </section>
      </div>
    );
  }

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const StatCard = ({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number | undefined; color: string }) => (
    <div className="card" style={{ padding: '1.5rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
      <div style={{
        width: '48px',
        height: '48px',
        borderRadius: '12px',
        background: `${color}15`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        color,
        flexShrink: 0,
      }}>
        {icon}
      </div>
      <div>
        <div className="text-2xl" style={{ fontWeight: 700, lineHeight: 1.2 }}>
          {statsLoading ? '...' : (value ?? 0)}
        </div>
        <div className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</div>
      </div>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <section className="card" style={{ padding: '2.5rem 2rem' }}>
        <h1 className="text-2xl" style={{ marginBottom: '0.5rem', fontWeight: 700 }}>
          {getGreeting()}, {user.full_name}
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Here&apos;s an overview of your system.
        </p>
      </section>

      {['admin', 'teacher'].includes(user.role) && (
        <>
          <div className="grid grid-cols-3" style={{ gap: '1rem' }}>
            <StatCard
              icon={<IconExams style={{ width: '24px', height: '24px' }} />}
              label="Total Exams"
              value={stats?.total_exams}
              color="var(--accent-primary)"
            />
            <StatCard
              icon={<IconStudents style={{ width: '24px', height: '24px' }} />}
              label="Total Students"
              value={stats?.total_students}
              color="var(--accent-success)"
            />
            <StatCard
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 2v4" />
                  <path d="M12 18v4" />
                  <path d="M4.93 4.93l2.83 2.83" />
                  <path d="M16.24 16.24l2.83 2.83" />
                  <path d="M2 12h4" />
                  <path d="M18 12h4" />
                  <path d="M4.93 19.07l2.83-2.83" />
                  <path d="M16.24 7.76l2.83-2.83" />
                </svg>
              }
              label="Pending Grading"
              value={stats?.pending_sheets}
              color="var(--accent-warning)"
            />
            <StatCard
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              }
              label="Completed Sheets"
              value={stats?.graded_sheets}
              color="var(--accent-success)"
            />
            <StatCard
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              }
              label="Active Batches"
              value={stats?.active_batches}
              color="var(--accent-info)"
            />
            <StatCard
              icon={<IconSchemas style={{ width: '24px', height: '24px' }} />}
              label="Total Gradings"
              value={stats?.total_gradings}
              color="var(--warning)"
            />
          </div>

          <section className="panel" style={{ padding: '2rem' }}>
            <div className="section-header">
              <h2 className="text-xl" style={{ fontWeight: 600 }}>School Management</h2>
              <span className="section-badge">Manage</span>
            </div>
            <div className="grid grid-cols-3" style={{ marginTop: '1.5rem' }}>
              <Link href="/users" className="card" style={{ display: 'block', textDecoration: 'none' }}>
                <IconUsers style={{ width: '32px', height: '32px', marginBottom: '0.75rem', color: 'var(--accent-primary)' }} />
                <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Users</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Manage teachers and admins</p>
              </Link>
              <Link href="/students" className="card" style={{ display: 'block', textDecoration: 'none' }}>
                <IconStudents style={{ width: '32px', height: '32px', marginBottom: '0.75rem', color: 'var(--accent-primary)' }} />
                <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Students</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>View, filter, edit, and bulk import students</p>
              </Link>
              <Link href="/classes" className="card" style={{ display: 'block', textDecoration: 'none' }}>
                <IconClasses style={{ width: '32px', height: '32px', marginBottom: '0.75rem', color: 'var(--accent-primary)' }} />
                <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Classes</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Create classes and assign teachers</p>
              </Link>
              <Link href="/subjects" className="card" style={{ display: 'block', textDecoration: 'none' }}>
                <IconSubjects style={{ width: '32px', height: '32px', marginBottom: '0.75rem', color: 'var(--accent-primary)' }} />
                <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Subjects</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Manage subjects per class with teacher assignments</p>
              </Link>
              <Link href="/exams" className="card" style={{ display: 'block', textDecoration: 'none' }}>
                <IconExams style={{ width: '32px', height: '32px', marginBottom: '0.75rem', color: 'var(--accent-primary)' }} />
                <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Exams</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Create and manage exams</p>
              </Link>
              <Link href="/result-schemas" className="card" style={{ display: 'block', textDecoration: 'none' }}>
                <IconSchemas style={{ width: '32px', height: '32px', marginBottom: '0.75rem', color: 'var(--accent-primary)' }} />
                <h3 className="text-md" style={{ fontWeight: 600, marginBottom: '0.5rem' }}>Result Schemas</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Define grading result structures</p>
              </Link>
            </div>
          </section>
        </>
      )}

      {user.role === 'student' && (
        <div className="grid grid-cols-3" style={{ gap: '1rem' }}>
          <StatCard
            icon={<IconExams style={{ width: '24px', height: '24px' }} />}
            label="Total Exams"
            value={stats?.total_exams}
            color="var(--accent-primary)"
          />
          <StatCard
            icon={
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
            }
            label="Pending Results"
            value={stats?.pending_results}
            color="var(--accent-warning)"
          />
          <StatCard
            icon={
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            }
            label="Published Results"
            value={stats?.published_results}
            color="var(--accent-success)"
          />
        </div>
      )}
    </div>
  );
}
