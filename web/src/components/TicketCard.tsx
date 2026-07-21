import { Link } from 'react-router-dom';
import { StampBadge } from './StampBadge';
import type { TourListItem } from '../api/types';

export function TicketCard({ tour }: { tour: TourListItem }) {
  const priceLabel = tour.is_free ? 'FREE' : `\u20b9${(tour.price_paise / 100).toFixed(0)}`;

  return (
    <Link
      to={`/tours/${tour.id}`}
      className="group relative flex bg-paper border-2 border-kaapi/15 rounded-md overflow-hidden
        shadow-[3px_3px_0_0_rgba(43,29,20,0.12)] hover:shadow-[5px_5px_0_0_rgba(154,51,36,0.25)]
        hover:-translate-y-0.5 hover:border-oxide/40 transition-all duration-150"
    >
      {/* Tear-off strip along the top, like detaching from a ticket booklet */}
      <div className="absolute top-0 left-0 right-0 h-2 bg-oxide/70 ticket-perforation" aria-hidden />

      {/* Main stub */}
      <div className="flex-1 p-5 pt-6 min-w-0">
        <p className="font-mono text-[10px] tracking-[0.2em] text-kaapi/50 uppercase mb-1">
          {tour.city} \u00b7 Walking pass
        </p>
        <h3 className="font-display text-xl font-semibold text-kaapi leading-snug pr-2">{tour.name}</h3>
        {tour.description && (
          <p className="font-body text-sm text-kaapi/70 mt-2 line-clamp-2">{tour.description}</p>
        )}
        <div className="mt-4">
          <StampBadge status={tour.status} />
        </div>
      </div>

      {/* Perforated tear line */}
      <div className="relative w-px bg-transparent">
        <div
          className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-px border-l-2 border-dashed border-kaapi/20"
          aria-hidden
        />
      </div>

      {/* Stub end */}
      <div className="w-28 shrink-0 flex flex-col items-center justify-center gap-1 p-3 bg-sandstone2/40">
        <span className="font-mono text-lg font-bold text-oxide">{priceLabel}</span>
        <span className="font-mono text-[11px] text-kaapi/60">
          {tour.duration_min ? `${tour.duration_min}m` : '\u2014'}
        </span>
        <span className="font-mono text-[11px] text-kaapi/60">
          {tour.distance_km ? `${tour.distance_km}km` : ''}
        </span>
        <span className="font-mono text-[11px] text-kaapi/40 mt-1">\u2665 {tour.like_count}</span>
      </div>
    </Link>
  );
}
