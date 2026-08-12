"use client";

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/lib/auth';
import { apiGet } from '@/lib/api';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import IconChevronDown from '@/components/icons/IconChevronDown';
import UploadStep from './components/UploadStep';
import MappingStep from './components/MappingStep';
import DoneStep from './components/DoneStep';

interface Exam {
  id: string;
  title: string;
  subject_id: string;
  class_id: string;
  status: string;
}

type WizardStep = 'upload' | 'mapping' | 'done';

export default function ExamUploadPage() {
  const { user, loading: authLoading } = useAuth();
  const params = useParams();
  const examId = params.id as string;

  const [exam, setExam] = useState<Exam | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<WizardStep>('upload');
  const [hasUploaded, setHasUploaded] = useState(false);

  const loadExam = useCallback(async () => {
    try {
      const data = await apiGet<Exam>(`/exams/${examId}/`);
      setExam(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load exam');
    } finally {
      setLoading(false);
    }
  }, [examId]);

  useEffect(() => {
    if (!authLoading && user && ['admin', 'teacher'].includes(user.role!)) {
      loadExam();
    } else if (!authLoading && (!user || !['admin', 'teacher'].includes(user.role!))) {
      setLoading(false);
    }
  }, [examId, user, authLoading, loadExam]);

  const handleUploadComplete = () => {
    setHasUploaded(true);
  };

  const handleNavigateToMapping = () => {
    setCurrentStep('mapping');
  };

  const handleMappingComplete = () => {
    setCurrentStep('done');
  };

  const handleBackToMapping = () => {
    setCurrentStep('mapping');
  };

  if (authLoading || loading) {
    return <div style={{ textAlign: 'center', padding: '2rem' }}>Loading...</div>;
  }

  if (!user || !['admin', 'teacher'].includes(user.role!)) {
    return <div>Access denied</div>;
  }

  if (!exam) {
    return <div>Exam not found</div>;
  }

  const steps: { key: WizardStep; label: string; num: number }[] = [
    { key: 'upload', label: 'Upload', num: 1 },
    { key: 'mapping', label: 'Mapping', num: 2 },
    { key: 'done', label: 'Done', num: 3 },
  ];

  return (
    <div>
      <div style={{ marginBottom: '1.5rem' }}>
        <Link href={`/exams/${examId}`} className="btn btn-secondary" style={{ marginBottom: '0.75rem' }}>
          Back to Exam
        </Link>
        <h1 className="text-lg" style={{ marginBottom: '0.25rem', fontWeight: 600 }}>{exam.title} &mdash; Upload Sheets</h1>
      </div>

      {error && (
        <div className="error-message" style={{ marginBottom: '1rem' }}>
          {error}
          <button onClick={() => setError(null)} style={{ float: 'right', background: 'none', border: 'none', color: 'inherit', cursor: 'pointer' }}>&times;</button>
        </div>
      )}

      <div className="wizard-steps">
        {steps.map((step, i) => {
          const isActive = step.key === currentStep;
          const isCompleted =
            (step.key === 'upload' && (hasUploaded || currentStep !== 'upload')) ||
            (step.key === 'mapping' && currentStep === 'done');
          return (
            <div key={step.key} style={{ display: 'contents' }}>
              <div className={`wizard-step ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
                <span className="wizard-step-num">{isCompleted ? <IconChevronDown style={{ transform: 'rotate(-90deg)' }} /> : step.num}</span>
                {step.label}
              </div>
              {i < steps.length - 1 && (
                <div className={`wizard-connector ${isCompleted ? 'completed' : ''}`} />
              )}
            </div>
          );
        })}
      </div>

      <div className="panel" style={{ padding: '1.5rem' }}>
        {currentStep === 'upload' && (
          <UploadStep
            examId={examId}
            onUploadComplete={handleUploadComplete}
            onNavigateToMapping={handleNavigateToMapping}
          />
        )}
        {currentStep === 'mapping' && (
          <MappingStep examId={examId} onComplete={handleMappingComplete} />
        )}
        {currentStep === 'done' && (
          <DoneStep examId={examId} onBackToMapping={handleBackToMapping} />
        )}
      </div>
    </div>
  );
}
