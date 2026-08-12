"use client";

import { QuestionPaperCrop, getCropImageUrl, deleteCrop } from '@/lib/api';

interface AttachedImagesSectionProps {
  examId: string;
  crops: QuestionPaperCrop[];
  onRemove?: (cropId: string) => void;
}

export default function AttachedImagesSection({
  examId,
  crops,
  onRemove,
}: AttachedImagesSectionProps) {
  if (crops.length === 0) return null;

  const handleRemove = async (cropId: string) => {
    try {
      await deleteCrop(examId, cropId);
      onRemove?.(cropId);
    } catch (err) {
      console.error('Failed to delete crop:', err);
    }
  };

  return (
    <div style={{ marginTop: '0.75rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <label style={{ fontSize: '0.8rem', color: 'var(--muted)', fontWeight: 600 }}>
          Attached Images ({crops.length})
        </label>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        {crops.map((crop) => (
          <div
            key={crop.id}
            style={{
              position: 'relative',
              width: '80px',
              height: '80px',
              borderRadius: '4px',
              overflow: 'hidden',
              border: '1px solid var(--border)',
              background: 'var(--surface2)',
            }}
          >
            <img
              src={getCropImageUrl(examId, crop.id)}
              alt={`Crop for Q${crop.q_no}`}
              style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            />
            <button
              onClick={() => handleRemove(crop.id)}
              style={{
                position: 'absolute',
                top: '2px',
                right: '2px',
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                background: 'rgba(239, 68, 68, 0.9)',
                color: 'white',
                border: 'none',
                cursor: 'pointer',
                fontSize: '0.7rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 0,
              }}
              title="Remove attachment"
            >
              ×
            </button>
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                background: 'rgba(0,0,0,0.7)',
                color: 'white',
                fontSize: '0.65rem',
                textAlign: 'center',
                padding: '2px 0',
              }}
            >
              Pg {crop.page_no}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
