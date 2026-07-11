/**
 * Risk grading is binary (High vs. everything else) — see docs/design_spec.md.
 * `variant` stays a map (rather than a single hardcoded class) so a future
 * tier, if ever reintroduced, only needs a new entry here.
 */
const VARIANT_CLASSES = {
  high: 'bg-risk-high-bg text-risk-high-text',
};

export default function Badge({ variant = 'high', children, className = '' }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-[3px] text-[11px] font-medium ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
