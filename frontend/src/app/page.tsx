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
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '60vh' }}>
        <div style={{
          width: '36px',
          height: '36px',
          border: '3px solid var(--border-subtle)',
          borderTopColor: 'var(--accent-primary)',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite'
        }} />
        <style jsx>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }

  // ============================================================
  // Unauthenticated Visitors: Professional Public Landing Page
  // ============================================================
  if (!user) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4rem', paddingBottom: '3rem' }}>
        {/* Hero Section */}
        <section style={{
          position: 'relative',
          padding: '4rem 2rem',
          borderRadius: 'var(--radius-xl)',
          background: 'linear-gradient(135deg, rgba(37,99,235,0.08) 0%, rgba(124,58,237,0.06) 50%, rgba(16,185,129,0.05) 100%)',
          border: '1px solid var(--border-subtle)',
          overflow: 'hidden',
          textAlign: 'center',
          boxShadow: 'var(--shadow-lg)'
        }}>
          {/* Subtle Background Glow Accent */}
          <div style={{
            position: 'absolute',
            top: '-50%',
            left: '50%',
            transform: 'translateX(-50%)',
            width: '600px',
            height: '300px',
            background: 'radial-gradient(circle, rgba(37,99,235,0.15) 0%, rgba(0,0,0,0) 70%)',
            pointerEvents: 'none',
            zIndex: 0
          }} />

          <div style={{ position: 'relative', zIndex: 1, maxWidth: '850px', margin: '0 auto' }}>
            {/* Pill Badge */}
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.4rem 1rem',
              borderRadius: 'var(--radius-full)',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-default)',
              fontSize: '0.85rem',
              fontWeight: 600,
              color: 'var(--accent-primary)',
              marginBottom: '1.5rem',
              boxShadow: 'var(--shadow-sm)'
            }}>
              <span>✦</span> AI-Powered Evaluation Pipeline v2.0
            </div>

            {/* Main Headline */}
            <h1 style={{
              fontSize: '2.75rem',
              fontWeight: 800,
              lineHeight: 1.25,
              letterSpacing: '-0.02em',
              marginBottom: '1.25rem',
              color: 'var(--text-primary)'
            }}>
              Transform Answer Sheet Evaluation with <span style={{
                background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>Vision AI</span>
            </h1>

            {/* Sub-headline */}
            <p style={{
              fontSize: '1.1rem',
              lineHeight: 1.6,
              color: 'var(--text-secondary)',
              marginBottom: '2.5rem',
              maxWidth: '720px',
              marginLeft: 'auto',
              marginRight: 'auto'
            }}>
              Automate handwritten and printed student paper grading. Digitate ZIP uploads, extract question rubrics, auto-match roll numbers, and grade at scale with Gemini 2.5 &amp; OpenAI.
            </p>

            {/* CTA Buttons */}
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
              <Link href="/login" className="btn btn-primary" style={{
                padding: '0.85rem 2rem',
                fontSize: '1rem',
                fontWeight: 600,
                borderRadius: 'var(--radius-md)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                boxShadow: '0 4px 14px rgba(37, 99, 235, 0.3)'
              }}>
                Sign In to Portal
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14" />
                  <path d="M12 5l7 7-7 7" />
                </svg>
              </Link>
              <a href="#features" className="btn" style={{
                padding: '0.85rem 1.75rem',
                fontSize: '1rem',
                fontWeight: 600,
                borderRadius: 'var(--radius-md)',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-primary)'
              }}>
                Explore Platform Features
              </a>
            </div>

            {/* Feature Metrics Badges */}
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              gap: '2rem',
              marginTop: '3rem',
              paddingTop: '2rem',
              borderTop: '1px solid var(--border-subtle)',
              flexWrap: 'wrap'
            }}>
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--accent-primary)' }}>10x</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Faster Evaluation</div>
              </div>
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--success)' }}>99.4%</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Auto-Match Accuracy</div>
              </div>
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--warning)' }}>Dual AI</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Gemini &amp; OpenAI</div>
              </div>
              <div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>100%</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Audit Trail Control</div>
              </div>
            </div>
          </div>
        </section>

        {/* 4-Step Pipeline Section */}
        <section id="workflow">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>
              How the Evaluation Pipeline Works
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
              An end-to-end automated workflow built for teachers and institute administrators.
            </p>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '1.5rem'
          }}>
            {[
              {
                step: '01',
                title: 'Exam & Rubric Setup',
                desc: 'Upload reference question papers, set total marks, and define AI result schemas with custom keywords & criteria.',
                color: '#2563eb'
              },
              {
                step: '02',
                title: 'Bulk ZIP Sheet Upload',
                desc: 'Upload compressed student answer sheet PDFs. The engine rasterizes HD canvas pages and extracts student roll numbers.',
                color: '#7c3aed'
              },
              {
                step: '03',
                title: 'AI Batch Evaluation',
                desc: 'Asynchronously dispatch grading jobs to Google Gemini 2.5 Flash / GPT-4o. Track real-time progress via poller.',
                color: '#d97706'
              },
              {
                step: '04',
                title: 'Review & Publish Scores',
                desc: 'Inspect AI score breakdowns side-by-side with student sheet scans, override marks if needed, and publish results.',
                color: '#16a34a'
              }
            ].map((s, idx) => (
              <div key={idx} className="card" style={{
                padding: '1.75rem',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.75rem',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-subtle)',
                background: 'var(--bg-secondary)',
                transition: 'transform var(--transition-fast), box-shadow var(--transition-fast)'
              }}>
                <div style={{
                  fontSize: '0.85rem',
                  fontWeight: 800,
                  color: s.color,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase'
                }}>
                  Step {s.step}
                </div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>{s.title}</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {s.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Features Grid Section */}
        <section id="features">
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>
              Enterprise Features Built for Scalability
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
              Everything you need to digitize examination workflows with confidence.
            </p>
          </div>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
            gap: '1.5rem'
          }}>
            {[
              {
                icon: (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="3" y="3" width="18" height="18" rx="2" />
                    <path d="M7 7h10M7 12h10M7 17h6" />
                  </svg>
                ),
                title: 'Vision Question Paper Extraction',
                desc: 'Extract questions, sub-parts, and diagram references automatically from PDF question papers using Vision LLMs.'
              },
              {
                icon: (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="8.5" cy="7" r="4" />
                    <polyline points="17 11 19 13 23 9" />
                  </svg>
                ),
                title: 'Smart Student Roll Matching',
                desc: 'Fuzzy matching engine links scanned student names & roll numbers on cover pages to enrolled class rosters.'
              },
              {
                icon: (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="2" y="3" width="20" height="14" rx="2" />
                    <line x1="8" y1="21" x2="16" y2="21" />
                    <line x1="12" y1="17" x2="12" y2="21" />
                  </svg>
                ),
                title: 'Split-Screen Review Canvas',
                desc: 'Side-by-side interactive viewer allows teachers to inspect AI scores per question, adjust marks, and log overrides.'
              },
              {
                icon: (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
                  </svg>
                ),
                title: 'Custom JSON Result Schemas',
                desc: 'Enforce strict schema validation on AI evaluation outputs with breakdown criteria, max marks, and feedback.'
              },
              {
                icon: (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                ),
                title: 'Role-Based Access Control',
                desc: 'Isolated workspaces for Administrators (full control), Teachers (class evaluation), and Students (view published results).'
              },
              {
                icon: (
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <line x1="18" y1="20" x2="18" y2="10" />
                    <line x1="12" y1="20" x2="12" y2="4" />
                    <line x1="6" y1="20" x2="6" y2="14" />
                  </svg>
                ),
                title: 'Analytics & Gradebook Export',
                desc: 'Real-time stats on pending sheets, graded batches, class averages, and exportable grade distribution data.'
              }
            ].map((f, i) => (
              <div key={i} className="card" style={{
                padding: '1.75rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border-subtle)',
                background: 'var(--bg-secondary)'
              }}>
                <div style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--accent-muted)',
                  color: 'var(--accent-primary)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {f.icon}
                </div>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>{f.title}</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* Role-Based Benefits */}
        <section style={{
          padding: '3rem 2rem',
          borderRadius: 'var(--radius-xl)',
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border-subtle)'
        }}>
          <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
            <h2 style={{ fontSize: '1.85rem', fontWeight: 700, marginBottom: '0.5rem' }}>
              Designed for Everyone in the Institute
            </h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1rem' }}>
              Tailored experiences for administrators, educators, and students.
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '2rem' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>🏫</span> School Administrators
              </div>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
                <li>✓ Centralized class, subject &amp; user management</li>
                <li>✓ Manage exam schedules &amp; result schema definitions</li>
                <li>✓ Monitor active LLM batch jobs &amp; system health</li>
              </ul>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>👨‍🏫</span> Educators &amp; Teachers
              </div>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
                <li>✓ Bulk upload student answer sheet ZIP files</li>
                <li>✓ Run AI auto-matching for student roll numbers</li>
                <li>✓ Review and override individual question scores</li>
              </ul>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>🎓</span> Enrolled Students
              </div>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.95rem', color: 'var(--text-secondary)' }}>
                <li>✓ Instant access to published digital grade sheets</li>
                <li>✓ Itemized mark breakdown per question</li>
                <li>✓ Transparent AI feedback &amp; teacher review status</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Bottom CTA Card */}
        <section style={{
          padding: '3rem 2rem',
          borderRadius: 'var(--radius-xl)',
          background: 'linear-gradient(135deg, var(--accent-primary) 0%, #1d4ed8 100%)',
          color: '#ffffff',
          textAlign: 'center',
          boxShadow: 'var(--shadow-xl)'
        }}>
          <h2 style={{ fontSize: '2rem', fontWeight: 800, marginBottom: '0.75rem' }}>
            Ready to Accelerate Answer Sheet Evaluation?
          </h2>
          <p style={{ fontSize: '1.05rem', opacity: 0.9, maxWidth: '600px', margin: '0 auto 2rem' }}>
            Sign in with your institute credentials to access your exam workspace and evaluation pipeline.
          </p>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', alignItems: 'center', flexWrap: 'wrap' }}>
            <Link href="/login" style={{
              padding: '0.85rem 2.25rem',
              fontSize: '1rem',
              fontWeight: 700,
              borderRadius: 'var(--radius-md)',
              background: '#ffffff',
              color: 'var(--accent-primary)',
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
              textDecoration: 'none'
            }}>
              Sign In to Portal
            </Link>
          </div>
          <div style={{ marginTop: '1.5rem', fontSize: '0.85rem', opacity: 0.8 }}>
            Default Admin Demo Login: <code>admin@school.edu</code> / <code>admin123</code>
          </div>
        </section>
      </div>
    );
  }

  // ============================================================
  // Authenticated Users: Interactive Dashboard
  // ============================================================
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
              label="Graded Sheets"
              value={stats?.graded_sheets}
              color="var(--accent-success)"
            />
            <StatCard
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                </svg>
              }
              label="Active LLM Batches"
              value={stats?.active_batches}
              color="var(--accent-info)"
            />
            <StatCard
              icon={
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              }
              label="Total Gradings"
              value={stats?.total_gradings}
              color="var(--accent-primary)"
            />
          </div>

          <section className="card" style={{ padding: '2rem' }}>
            <h2 className="text-lg" style={{ marginBottom: '1rem', fontWeight: 600 }}>Quick Actions</h2>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <Link href="/exams" className="btn btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <IconExams style={{ width: '18px', height: '18px' }} /> Manage Exams
              </Link>
              <Link href="/students" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                <IconStudents style={{ width: '18px', height: '18px' }} /> Manage Students
              </Link>
              {user.role === 'admin' && (
                <>
                  <Link href="/users" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <IconUsers style={{ width: '18px', height: '18px' }} /> User Management
                  </Link>
                  <Link href="/classes" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <IconClasses style={{ width: '18px', height: '18px' }} /> Classes
                  </Link>
                  <Link href="/subjects" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <IconSubjects style={{ width: '18px', height: '18px' }} /> Subjects
                  </Link>
                  <Link href="/result-schemas" className="btn btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                    <IconSchemas style={{ width: '18px', height: '18px' }} /> Result Schemas
                  </Link>
                </>
              )}
            </div>
          </section>
        </>
      )}

      {user.role === 'student' && (
        <div className="grid grid-cols-2" style={{ gap: '1rem' }}>
          <StatCard
            icon={<IconExams style={{ width: '24px', height: '24px' }} />}
            label="Published Results"
            value={stats?.published_results}
            color="var(--accent-success)"
          />
          <StatCard
            icon={<IconExams style={{ width: '24px', height: '24px' }} />}
            label="Pending Results"
            value={stats?.pending_results}
            color="var(--accent-warning)"
          />
        </div>
      )}
    </div>
  );
}
