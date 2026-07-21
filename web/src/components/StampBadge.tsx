import type { TourStatus } from '../api/types';

const LABELS: Record<TourStatus, string> = {
  not_purchased: 'UNBOOKED',
  purchased: 'BOOKED',
  in_progress: 'WALKING',
  completed_locked: 'COMPLETED',
};

const COLORS: Record<TourStatus, string> = {
  not_purchased: 'text-kaapi/40 border-kaapi/40',
  purchased: 'text-oxide border-oxide',
  in_progress: 'text-verdigris border-verdigris',
  completed_locked: 'text-kaapi/60 border-kaapi/60',
};

/** The tour-status badge, styled like a rough rubber ticket stamp — tying
 * directly into the product's real rule that a tour's license gets
 * "punched" exactly once. */
export function StampBadge({ status, className = '' }: { status: TourStatus; className?: string }) {
  return (
    <span
      className={`stamp inline-block border-2 rounded-sm px-2 py-0.5 font-mono text-[11px] tracking-widest uppercase ${COLORS[status]} ${className}`}
      style={{ WebkitTextStroke: '0.3px currentColor' }}
    >
      {LABELS[status]}
    </span>
  );
}
