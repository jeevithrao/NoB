import type { TourStatus } from '../api/types';

const LABELS: Record<TourStatus, string> = {
  not_purchased: 'AVAILABLE',
  purchased: 'READY TO WALK',
  in_progress: 'IN PROGRESS',
  completed_locked: 'COMPLETED',
};

const COLORS: Record<TourStatus, string> = {
  not_purchased: 'text-verdigris border-verdigris',
  purchased: 'text-turmeric border-turmeric',
  in_progress: 'text-oxide border-oxide',
  completed_locked: 'text-kaapi border-kaapi',
};

/** The tour-status badge, styled like a rubber stamp impression — tying
 * directly into the product's physical paper ticket aesthetic. */
export function StampBadge({ status, className = '' }: { status: TourStatus; className?: string }) {
  return (
    <span
      className={`stamp inline-block border-2 rounded px-2 py-0.5 font-mono text-[10px] tracking-[0.15em] uppercase ${COLORS[status]} ${className}`}
      style={{ WebkitTextStroke: '0.3px currentColor' }}
    >
      {LABELS[status]}
    </span>
  );
}
