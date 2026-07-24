/**
 * Covers the three button shapes in docs/prototype.html:
 * - "outline": upload option button (icon + label, bordered surface)
 * - "icon": topbar back button (icon-only, ghost)
 * - "send": chat input send button (icon-only, filled primary)
 *
 * Icon children should use stroke="currentColor" so they inherit the
 * variant's text color instead of a hardcoded stroke.
 */
const VARIANT_CLASSES = {
  outline:
    'flex items-center gap-2.5 rounded-xl border-[0.5px] border-border bg-surface px-7 py-3.5 text-text-primary hover:border-border-strong hover:bg-primary-subtle',
  icon: 'flex h-7 w-7 items-center justify-center rounded-md border-0 bg-transparent text-text-secondary hover:bg-primary-subtle',
  send: 'flex h-[34px] w-[34px] flex-shrink-0 items-center justify-center rounded-lg border-0 bg-primary text-white hover:bg-primary-hover',
};

export default function Button({ variant = 'outline', className = '', children, ...props }) {
  return (
    <button type="button" className={`cursor-pointer transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}
