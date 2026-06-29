import { useCallback, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

export default function Button({
  children,
  onClick,
  variant = 'primary',
  icon: Icon,
  isLoading = false,
  disabled = false,
  className = '',
  size = 'medium',
  type = 'button',
  cooldown = 1000,
  ...props
}) {
  const [inCooldown, setInCooldown] = useState(false);
  const useCooldown = cooldown > 0 && type !== 'submit' && typeof onClick === 'function';

  useEffect(() => () => setInCooldown(false), []);

  const handleClick = useCallback((event) => {
    if (disabled || isLoading || (useCooldown && inCooldown)) {
      event.preventDefault();
      return;
    }

    if (onClick) onClick(event);

    if (useCooldown) {
      setInCooldown(true);
      setTimeout(() => setInCooldown(false), cooldown);
    }
  }, [cooldown, disabled, inCooldown, isLoading, onClick, useCooldown]);

  const isDisabled = disabled || isLoading || (useCooldown && inCooldown);
  const finalClassName = [
    'button',
    `button-${variant}`,
    size === 'small' ? 'button-small' : '',
    size === 'large' ? 'button-large' : '',
    isDisabled ? 'is-disabled' : '',
    isLoading ? 'is-loading' : '',
    className,
  ].filter(Boolean).join(' ');

  return (
    <button
      type={type}
      className={finalClassName}
      onClick={handleClick}
      disabled={isDisabled}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="animate-spin" size={size === 'small' ? 14 : 18} />
      ) : (
        Icon && <Icon size={size === 'small' ? 16 : 20} />
      )}
      <span>{children}</span>
    </button>
  );
}