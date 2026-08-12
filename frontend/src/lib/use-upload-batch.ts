import { useState, useEffect, useRef } from 'react';
import { apiGet } from '@/lib/api';

interface UploadBatch {
  id: string;
  exam_id: string;
  uploaded_by: string | null;
  zip_filename: string;
  total_pdfs: number;
  processed_pdfs: number;
  status: string;
  created_at: string;
}

export function useUploadBatchPolling(examId: string, intervalMs: number = 2000) {
  const [batches, setBatches] = useState<UploadBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchBatches = async () => {
    try {
      const data = await apiGet<UploadBatch[]>(`/exams/${examId}/sheets/upload-batches`);
      setBatches(data);
      setError(null);

      const hasActiveBatch = data.some(
        (b) => b.status === 'extracting' || b.status === 'ready_for_mapping'
      );
      if (!hasActiveBatch && intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch upload batches');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();

    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    intervalRef.current = setInterval(fetchBatches, intervalMs);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [examId, intervalMs]);

  return { batches, loading, error, refetch: fetchBatches };
}
