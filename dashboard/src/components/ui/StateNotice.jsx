export default function StateNotice({
  icon: Icon,
  title,
  message,
  children,
  tone = 'neutral',
  compact = false,
  isLoading = false,
  className = '',
}) {
  const classes = [
    'state-notice',
    `state-notice--${tone}`,
    compact ? 'state-notice--compact' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <div className={classes}>
      {Icon && (
        <div className="state-notice__icon">
          <Icon className={isLoading ? 'animate-spin' : ''} size={compact ? 24 : 34} strokeWidth={1.8} />
        </div>
      )}
      {title && <div className="state-notice__title">{title}</div>}
      {message && <div className="state-notice__message">{message}</div>}
      {children && <div className="state-notice__actions">{children}</div>}
    </div>
  );
}