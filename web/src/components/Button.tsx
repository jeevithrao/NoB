import type { ButtonHTMLAttributes } from 'react';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  loading?: boolean;
}

const VARIANT_CLASSES: Record<string, string> = {
  primary: 'bg-oxide text-paper hover:bg-oxide-dark border-oxide',
  secondary: 'bg-transparent text-oxide border-oxide hover:bg-oxide/5',
  danger: 'bg-transparent text-verdigris-dark border-verdigris hover:bg-verdigris/5',
};

export function Button({ variant = 'primary', loading, disabled, className = '', children, ...rest }: Props) {
  return (
    <button
      disabled={disabled || loading}
      className={`inline-flex items-center justify-center gap-2 rounded-full border-2 px-6 py-3
        font-body font-semibold text-sm tracking-wide transition-colors
        disabled:opacity-50 disabled:cursor-not-allowed
        ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {loading ? 'Please wait…' : children}
    </button>
  );
}
