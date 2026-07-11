/**
 * LegaLenz wordmark. "Lenz" sits on a risk-high-bg highlight rect to echo
 * the clause-highlight visual language used throughout the product.
 */
export default function Logo({ variant = 'topbar', showLabel, className = '' }) {
  const { width, height } = variant === 'home' ? { width: 275, height: 75 } : { width: 140, height: 39 };
  const shouldShowLabel = showLabel ?? variant === 'topbar';

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <svg
        viewBox="-4 12 220 60"
        width={width}
        height={height}
        xmlns="http://www.w3.org/2000/svg"
        role="img"
        aria-label="LegaLenz"
      >
        <text x="0" y="58" className="fill-primary font-pretendard" fontSize="46" fontWeight="800" letterSpacing="-2.2">
          Lega
        </text>
        <rect x="108" y="34" width="104" height="26" className="fill-risk-high-bg" />
        <text x="112" y="58" className="fill-primary font-pretendard" fontSize="46" fontWeight="800" letterSpacing="-2.2">
          Lenz
        </text>
      </svg>
      {shouldShowLabel && <span className="text-xs font-normal text-text-secondary">계약서 리스크 분석</span>}
    </div>
  );
}
