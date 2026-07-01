import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import Button from '../components/ui/Button.jsx';

const ConfirmContext = createContext(null);

const DEFAULT_OPTIONS = {
  title: 'Potvrdenie',
  message: 'Ste si istí?',
  confirmText: 'Potvrdiť',
  cancelText: 'Zrušiť',
  type: 'warning',
};

export function ConfirmProvider({ children }) {
  const [options, setOptions] = useState(DEFAULT_OPTIONS);
  const [isOpen, setIsOpen] = useState(false);
  const resolveRef = useRef(null);

  const confirm = useCallback((params = {}) => {
    setOptions({ ...DEFAULT_OPTIONS, ...params });
    setIsOpen(true);
    return new Promise((resolve) => {
      resolveRef.current = resolve;
    });
  }, []);

  const close = useCallback((result) => {
    setIsOpen(false);
    if (resolveRef.current) {
      resolveRef.current(result);
      resolveRef.current = null;
    }
  }, []);

  const value = useMemo(() => ({ confirm }), [confirm]);

  return (
    <ConfirmContext.Provider value={value}>
      {children}
      {isOpen && (
        <div className="confirm-overlay" role="presentation">
          <div className="confirm-box" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
            <h3 id="confirm-title" className={`confirm-title ${options.type === 'danger' ? 'danger' : ''}`}>
              {options.title}
            </h3>
            <p className="confirm-message">{options.message}</p>
            <div className="confirm-actions">
              <Button variant="secondary" onClick={() => close(false)} cooldown={0}>
                {options.cancelText}
              </Button>
              <Button variant={options.type === 'danger' ? 'danger' : 'primary'} onClick={() => close(true)} cooldown={0}>
                {options.confirmText}
              </Button>
            </div>
          </div>
        </div>
      )}
    </ConfirmContext.Provider>
  );
}

export function useConfirm() {
  const value = useContext(ConfirmContext);
  if (!value) {
    throw new Error('useConfirm must be used inside ConfirmProvider');
  }
  return value;
}
