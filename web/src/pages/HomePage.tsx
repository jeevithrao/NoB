import { useEffect, useState } from 'react';
import { TicketCard } from '../components/TicketCard';
import { toursApi } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import type { TourListItem } from '../api/types';

export function HomePage() {
  const { user } = useAuth();
  const [tours, setTours] = useState<TourListItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    toursApi
      .list('Bangalore')
      .then(setTours)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      {/* Hero — the thesis: a walk is a ticket you punch stop by stop */}
      <section className="relative overflow-hidden border-b-2 border-kaapi/10">
        <div className="max-w-5xl mx-auto px-5 pt-16 pb-12">
          <p className="font-mono text-xs tracking-[0.25em] text-oxide uppercase mb-4">
            {user ? `Namaskara, ${user.full_name?.split(' ')[0] || 'walker'}` : 'Bangalore, on foot'}
          </p>
          <h1 className="font-display text-4xl sm:text-5xl font-semibold text-kaapi leading-[1.05] max-w-2xl">
            Every neighbourhood has a story.
            <br />
            <span className="text-oxide">Walk until you\u2019ve heard it.</span>
          </h1>
          <p className="text-kaapi/70 font-body mt-5 max-w-xl leading-relaxed">
            One ticket, one walk. Buy a pass, download it for offline listening, and let your
            location cue each stop\u2019s story as you reach it \u2014 markets, temples, and the
            bungalows in between.
          </p>
        </div>

        {/* Departure board — the recognisable, distinctive touch: neighbourhoods
            presented like a bus-stand destination board rather than photo tiles. */}
        <div className="bg-kaapi text-paper">
          <div className="max-w-5xl mx-auto px-5 py-3 flex flex-wrap gap-x-8 gap-y-2 font-mono text-xs tracking-widest uppercase overflow-x-auto">
            {['Malleshwaram', 'Basavanagudi', 'Cubbon Park', 'Gandhi Bazaar', 'Lalbagh'].map((n) => (
              <span key={n} className="text-paper/70">
                {n}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Ticket counter */}
      <section className="max-w-5xl mx-auto px-5 py-12">
        <h2 className="font-display text-2xl font-semibold text-kaapi mb-1">Available walks</h2>
        <p className="text-kaapi/60 text-sm mb-8">Bangalore</p>

        {loading ? (
          <p className="text-kaapi/50 font-mono text-sm">Loading tours\u2026</p>
        ) : tours.length === 0 ? (
          <p className="text-kaapi/50 font-mono text-sm">No tours published yet \u2014 check back soon.</p>
        ) : (
          <div className="flex flex-col gap-5">
            {tours.map((tour) => (
              <TicketCard key={tour.id} tour={tour} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
