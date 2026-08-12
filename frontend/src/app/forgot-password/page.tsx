'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiPost } from '@/lib/api';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await apiPost('/auth/forgot-password/', { email });
      setSubmitted(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }}>
      <div className="card" style={{ width: '100%', maxWidth: '420px' }}>
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <h1 className="text-2xl" style={{ fontWeight: 700, marginBottom: '0.5rem' }}>Reset Password</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
            {submitted ? 'Check your email (or contact admin for token)' : 'Enter your email to receive a reset token'}
          </p>
        </div>

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        {submitted ? (
          <div style={{ textAlign: 'center' }}>
            <p style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)' }}>If an account exists with that email, a reset token has been generated.</p>
            <button onClick={() => router.push('/login')} className="btn btn-primary">
              Back to Login
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label className="form-label" htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                className="form-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@school.edu"
                required
                disabled={submitting}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', marginTop: '1rem' }}
              disabled={submitting}
            >
              {submitting ? 'Sending...' : 'Send Reset Token'}
            </button>
          </form>
        )}

        <div style={{ marginTop: '2rem', textAlign: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '1.5rem' }}>
          <Link href="/login" style={{ color: 'var(--accent-primary)', fontSize: '0.875rem' }}>
            Back to login
          </Link>
        </div>
      </div>
    </div>
  );
}
