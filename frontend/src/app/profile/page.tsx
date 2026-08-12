'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useAuth } from '@/lib/auth';

export default function ProfilePage() {
  const { user, loading: authLoading } = useAuth();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!authLoading) {
      setLoading(false);
    }
  }, [authLoading]);

  if (loading) {
    return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Loading...</div>;
  }

  if (!user) {
    return (
      <div className="card" style={{ textAlign: 'center', padding: '3rem' }}>
        <p className="text-md" style={{ color: 'var(--text-secondary)' }}>Please sign in to view your profile.</p>
        <Link href="/login" className="btn btn-primary" style={{ marginTop: '1rem', display: 'inline-block' }}>
          Sign In
        </Link>
      </div>
    );
  }

  const InfoRow = ({ label, value }: { label: string; value: React.ReactNode }) => (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '1rem 0', borderBottom: '1px solid var(--border-subtle)' }}>
      <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <span className="text-sm" style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <section className="card" style={{ padding: '2.5rem 2rem' }}>
        <h1 className="text-2xl" style={{ marginBottom: '0.5rem', fontWeight: 700 }}>
          Profile
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem' }}>
          Manage your account information and settings.
        </p>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <section className="panel" style={{ padding: '2rem' }}>
          <h2 className="text-lg" style={{ fontWeight: 600, marginBottom: '1.5rem' }}>Account Details</h2>
          <InfoRow label="Full Name" value={user.full_name} />
          <InfoRow label="Email" value={user.email} />
          <InfoRow label="Role" value={user.role.charAt(0).toUpperCase() + user.role.slice(1)} />
          <InfoRow label="Status" value={
            <span className={user.is_active ? 's-published' : 's-failed'}>
              {user.is_active ? 'Active' : 'Inactive'}
            </span>
          } />
          <InfoRow label="Member Since" value={new Date(user.created_at).toLocaleDateString()} />
          {user.class_id && <InfoRow label="Class ID" value={user.class_id} />}
          {user.roll_no && <InfoRow label="Roll Number" value={user.roll_no} />}
        </section>

        <section className="panel" style={{ padding: '2rem' }}>
          <h2 className="text-lg" style={{ fontWeight: 600, marginBottom: '1.5rem' }}>Security</h2>
          <p className="text-sm" style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
            Manage your password and security settings.
          </p>
          <Link href="/change-password" className="btn btn-primary">
            Change Password
          </Link>
        </section>
      </div>
    </div>
  );
}
