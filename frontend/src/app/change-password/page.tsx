'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { apiPost } from '@/lib/api';

export default function ChangePasswordPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  const [current, setCurrent] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirm, setConfirm] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (newPass !== confirm) {
      setError('New passwords do not match');
      return;
    }
    if (newPass.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    setSubmitting(true);
    try {
      await apiPost('/auth/change-password/', {
        current_password: current,
        new_password: newPass,
      });
      setSuccess(true);
      setTimeout(() => router.push('/'), 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Change failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', marginTop: '4rem' }}>Loading...</div>;
  }

  if (!user) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
        <div className="card" style={{ width: '100%', maxWidth: '420px', textAlign: 'center' }}>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>You must be logged in to change your password.</p>
          <Link href="/login" className="btn btn-primary">Log In</Link>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '420px' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 className="text-2xl" style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Change Password</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            Logged in as <strong>{user.email}</strong>
          </p>
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {success ? (
          <div style={{ textAlign: 'center' }}>
            <div style={{
              background: 'var(--success-bg)',
              border: '1px solid var(--success)',
              color: 'var(--success-text)',
              padding: '1rem',
              borderRadius: 'var(--radius-md)',
              marginBottom: '1rem',
              fontSize: '0.875rem',
            }}>
              Password changed successfully! Redirecting...
            </div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="current">Current password</label>
              <input
                id="current"
                type="password"
                className="form-input"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="new">New password</label>
              <input
                id="new"
                type="password"
                className="form-input"
                value={newPass}
                onChange={(e) => setNewPass(e.target.value)}
                required
                minLength={6}
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="confirm">Confirm new password</label>
              <input
                id="confirm"
                type="password"
                className="form-input"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                minLength={6}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '1rem' }}
              disabled={submitting}
            >
              {submitting ? 'Updating...' : 'Update Password'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
