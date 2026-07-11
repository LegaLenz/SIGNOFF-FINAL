import { useCallback, useEffect } from 'react';

const LEAVE_CONFIRM_MESSAGE = '분석 화면을 벗어나면 현재 결과가 사라집니다. 계속할까요?';

/**
 * Implements CLAUDE.md's "no server-side history" reset policy for the
 * analysis screen (docs/design_spec.md), mirroring docs/prototype.html's
 * beforeunload listener + back-btn confirm() dialog.
 *
 * `isActive` is caller-provided rather than derived here — screen-state
 * management doesn't exist yet (pending the assembly step), so this hook
 * has no opinion on which screen is current.
 */
export function useSessionReset({ isActive, onReset }) {
  useEffect(() => {
    if (!isActive) return;

    const handleBeforeUnload = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [isActive]);

  const confirmAndReset = useCallback(() => {
    if (window.confirm(LEAVE_CONFIRM_MESSAGE)) {
      onReset?.();
    }
  }, [onReset]);

  return confirmAndReset;
}
