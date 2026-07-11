import { useEffect, useRef, useState } from 'react';

const STEP_LABELS = {
  image: ['이미지에서 텍스트 추출 중...', '조항 단위로 분리하는 중...', '리스크 등급 분류하는 중...'],
  pdf: ['PDF에서 텍스트 추출 중...', '조항 단위로 분리하는 중...', '리스크 등급 분류하는 중...'],
};

const STEP_INTERVAL_MS = 700;

export default function Processing({ fileName, fileType, estimatedSeconds, onComplete }) {
  const steps = fileType?.startsWith('image/') ? STEP_LABELS.image : STEP_LABELS.pdf;

  const [stepIndex, setStepIndex] = useState(0);
  const [prevSteps, setPrevSteps] = useState(steps);
  if (steps !== prevSteps) {
    setPrevSteps(steps);
    setStepIndex(0);
  }

  const onCompleteRef = useRef(onComplete);

  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      i += 1;
      if (i < steps.length) {
        setStepIndex(i);
      } else {
        clearInterval(interval);
        onCompleteRef.current?.();
      }
    }, STEP_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [steps]);

  const estimatedMinutes = estimatedSeconds != null ? Math.ceil(estimatedSeconds / 60) : null;

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="text-center">
        <div className="mx-auto mb-5 h-8 w-8 animate-spin rounded-full border-[2.5px] border-border border-t-primary" />
        <p className="mb-1.5 text-sm font-medium text-text-primary">계약서를 분석하고 있어요</p>
        <p className="min-h-[18px] text-[12.5px] text-text-secondary">{steps[stepIndex]}</p>
        {estimatedMinutes != null && (
          <p className="mt-1 text-[12.5px] text-text-secondary">약 {estimatedMinutes}분 소요 예상</p>
        )}
        {fileName && <p className="mt-4 text-xs text-text-disabled">{fileName}</p>}
      </div>
    </div>
  );
}
