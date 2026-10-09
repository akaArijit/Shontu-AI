'use client';

import { forwardRef, InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, id, ...props }, ref) => {
    const checkboxId = id || label?.toLowerCase().replace(/\s+/g, '-');

    return (
      <label className={cn('flex items-center gap-2 cursor-pointer', className)}>
        <input
          ref={ref}
          type="checkbox"
          id={checkboxId}
          className={cn(
            'w-4 h-4 rounded border-neutral-300 text-primary-600',
            'focus:ring-2 focus:ring-primary-500 focus:ring-offset-2',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-colors'
          )}
          {...props}
        />
        {label && (
          <span className="text-sm text-neutral-700 select-none">{label}</span>
        )}
      </label>
    );
  }
);

Checkbox.displayName = 'Checkbox';