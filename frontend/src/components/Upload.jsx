import { useRef, useState } from 'react';
import Logo from './common/Logo';
import Button from './common/Button';

const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];

const MAX_SIZE_BYTES = {
  'application/pdf': 10 * 1024 * 1024,
  'image/jpeg': 5 * 1024 * 1024,
  'image/png': 5 * 1024 * 1024,
  'image/webp': 5 * 1024 * 1024,
};

const MAX_SIZE_LABEL = {
  'application/pdf': '10MB',
  'image/jpeg': '5MB',
  'image/png': '5MB',
  'image/webp': '5MB',
};

function validateFile(file) {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return '지원하지 않는 파일 형식입니다. PDF, JPG, PNG, WEBP 파일만 업로드할 수 있어요.';
  }
  if (file.size > MAX_SIZE_BYTES[file.type]) {
    return `파일 크기 초과: ${MAX_SIZE_LABEL[file.type]} 이하만 허용됩니다`;
  }
  return null;
}

export default function Upload({ onFileSelected }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState(null);
  const pdfInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  const handleFile = (file) => {
    if (!file) return;
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    onFileSelected?.(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleInputChange = (e) => {
    handleFile(e.target.files[0]);
    e.target.value = '';
  };

  return (
    <div className="flex h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-[480px] text-center">
        <div className="mb-2.5 flex justify-center">
          <Logo variant="home" />
        </div>
        <p className="mb-10 text-[13px] text-text-secondary">계약서를 업로드하면 1분 안에 위험 조항을 찾아드려요</p>

        <div
          role="button"
          tabIndex={0}
          className={`cursor-pointer rounded-2xl border-[1.5px] border-dashed px-8 py-12 transition-colors duration-150 ${
            isDragOver ? 'border-primary bg-primary-subtle' : 'border-border bg-surface hover:border-primary hover:bg-primary-subtle'
          }`}
          onClick={() => pdfInputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && pdfInputRef.current?.click()}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <div className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-full bg-primary-subtle">
            <svg
              viewBox="0 0 24 24"
              width="20"
              height="20"
              fill="none"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="stroke-primary"
            >
              <path d="M4 14.9A5 5 0 0 1 6 5.3 6 6 0 0 1 17.7 7 4.5 4.5 0 0 1 18 16" />
              <path d="M12 12v9" />
              <path d="m16 16-4-4-4 4" />
            </svg>
          </div>
          <p className="mb-1 text-sm font-medium text-text-primary">파일을 여기에 끌어다 놓으세요</p>
          <p className="text-[12.5px] text-text-secondary">PDF 또는 이미지 · 클릭해서 파일 선택</p>
        </div>

        {error && (
          <p role="alert" className="mt-3 rounded-lg bg-risk-high-bg px-3 py-2 text-xs text-risk-high-text">
            {error}
          </p>
        )}

        <div className="my-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <span className="text-[11.5px] text-text-disabled">또는</span>
          <div className="h-px flex-1 bg-border" />
        </div>

        <div className="flex justify-center">
          <Button variant="outline" onClick={() => cameraInputRef.current?.click()}>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
              <circle cx="12" cy="13" r="3.5" />
            </svg>
            <span className="text-[12.5px] font-medium">카메라로 촬영</span>
          </Button>
        </div>

        <p className="mt-7 text-[11.5px] leading-[1.6] text-text-disabled">
          PDF(10MB) · JPG/PNG/WEBP(5MB) 지원 · 계약서를 평평하게 펴서 촬영하면 인식률이 높아져요
          <br />
          본 서비스는 법률 자문이 아닌 참고용입니다
        </p>

        <input
          ref={pdfInputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={handleInputChange}
        />
        <input
          ref={cameraInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          className="hidden"
          onChange={handleInputChange}
        />
      </div>
    </div>
  );
}
