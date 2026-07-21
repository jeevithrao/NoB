import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { toursApi, sessionsApi } from '../api/endpoints';
import { distanceMeters } from '../lib/geo';
import { uuidv4 } from '../lib/uuid';
import { queueSessionEvent, getQueuedEvents, clearQueuedEvents } from '../lib/offlineQueue';
import type { StopWithAudio, TourPackage } from '../api/types';

type Phase = 'loading' | 'route_to_start' | 'walking' | 'finishing' | 'error';

export function WalkPage() {
  const { tourId } = useParams<{ tourId: string }>();
  const navigate = useNavigate();

  const [phase, setPhase] = useState<Phase>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [pkg, setPkg] = useState<TourPackage | null>(null);
  const [distanceToNext, setDistanceToNext] = useState<number | null>(null);
  const [visited, setVisited] = useState<Set<string>>(new Set());
  const [activeStop, setActiveStop] = useState<StopWithAudio | null>(null);

  const visitedRef = useRef<Set<string>>(new Set());
  const watchId = useRef<number | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const pkgRef = useRef<TourPackage | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!tourId) return;
    (async () => {
      try {
        const detail = await toursApi.get(tourId);
        const session = await sessionsApi.createOrResume(tourId);
        const tourPackage = await toursApi.getPackage(tourId);
        setPkg(tourPackage);
        pkgRef.current = tourPackage;
        sessionIdRef.current = session.id;

        // Mark stops the backend already recorded as visited (e.g. resuming
        // after closing the tab) as already done.
        void detail;
        setPhase('route_to_start');
      } catch (err: any) {
        setErrorMessage(err?.message || 'Could not start this walk.');
        setPhase('error');
      }
    })();

    return () => {
      if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    };
  }, [tourId]);

  const flushQueuedEvents = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid) return;
    const queued = getQueuedEvents(sid);
    if (queued.length === 0) return;
    try {
      await sessionsApi.submitEventsBatch(sid, queued);
      clearQueuedEvents(sid);
    } catch {
      // Stays queued — client_event_id makes a later retry safe.
    }
  }, []);

  const handleCompleteWalk = useCallback(async () => {
    const sid = sessionIdRef.current;
    if (!sid || !tourId) return;
    setPhase('finishing');
    try {
      await flushQueuedEvents();
      await sessionsApi.complete(sid);
      navigate(`/tours/${tourId}/complete`);
    } catch (err: any) {
      setErrorMessage(err?.message || 'Could not confirm completion. Try again.');
      setPhase('walking');
    }
  }, [tourId, navigate, flushQueuedEvents]);

  const playStopAudio = useCallback(
    async (stop: StopWithAudio) => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      setActiveStop(stop);

      queueSessionEvent(sid, {
        client_event_id: uuidv4(),
        stop_id: stop.id,
        event_type: 'audio_started',
        occurred_at: new Date().toISOString(),
      });

      if (audioRef.current) {
        audioRef.current.src = stop.audio_url;
        audioRef.current.play().catch(() => {
          // Autoplay can be blocked by the browser — the stop still counts
          // as visited; the person can press play manually.
        });
      }
      await flushQueuedEvents();
    },
    [flushQueuedEvents]
  );

  const handleArrivedAtStop = useCallback(
    async (stop: StopWithAudio) => {
      if (visitedRef.current.has(stop.id)) return;
      visitedRef.current.add(stop.id);
      setVisited(new Set(visitedRef.current));

      const sid = sessionIdRef.current;
      if (sid) {
        queueSessionEvent(sid, {
          client_event_id: uuidv4(),
          stop_id: stop.id,
          event_type: 'arrived',
          occurred_at: new Date().toISOString(),
        });
      }

      await playStopAudio(stop);

      const allStops = pkgRef.current?.stops ?? [];
      const allVisited = allStops.length > 0 && allStops.every((s) => visitedRef.current.has(s.id));
      if (allVisited) {
        await handleCompleteWalk();
      }
    },
    [playStopAudio, handleCompleteWalk]
  );

  function startWatchingLocation() {
    if (!navigator.geolocation) {
      setErrorMessage('This browser does not support geolocation.');
      setPhase('error');
      return;
    }
    setPhase('walking');

    watchId.current = navigator.geolocation.watchPosition(
      (position) => {
        const currentPkg = pkgRef.current;
        if (!currentPkg) return;
        const nextStop = currentPkg.stops.find((s) => !visitedRef.current.has(s.id));
        if (!nextStop) return;

        const distance = distanceMeters(
          position.coords.latitude,
          position.coords.longitude,
          parseFloat(nextStop.lat),
          parseFloat(nextStop.lng)
        );
        setDistanceToNext(distance);

        if (distance <= nextStop.trigger_radius_m) {
          handleArrivedAtStop(nextStop);
        }
      },
      (geoError) => {
        setErrorMessage(`Location error: ${geoError.message}. You can still play stops manually below.`);
      },
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 15000 }
    );
  }

  if (phase === 'loading') {
    return <p className="max-w-2xl mx-auto px-5 py-16 text-kaapi/50 font-mono text-sm">Preparing your walk\u2026</p>;
  }

  if (phase === 'error' && !pkg) {
    return (
      <div className="max-w-2xl mx-auto px-5 py-16 text-center">
        <p className="text-verdigris-dark font-body">{errorMessage}</p>
        <Button variant="secondary" className="mt-6" onClick={() => navigate(-1)}>
          Go back
        </Button>
      </div>
    );
  }

  if (!pkg) return null;

  if (phase === 'route_to_start') {
    const firstStop = pkg.stops[0];
    return (
      <div className="max-w-md mx-auto px-5 py-16 text-center">
        <p className="font-mono text-xs tracking-widest text-oxide uppercase mb-3">Stop 1 of {pkg.stops.length}</p>
        <h1 className="font-display text-2xl font-semibold text-kaapi">{firstStop.name}</h1>
        <p className="text-kaapi/70 mt-4 leading-relaxed">
          Head to the starting point. Once you\u2019re within range, narration begins automatically \u2014
          keep this tab open and location access allowed.
        </p>
        <Button className="mt-8 w-full" onClick={startWatchingLocation}>
          I\u2019ve arrived \u2014 start the walk
        </Button>
      </div>
    );
  }

  // phase === 'walking' | 'finishing'
  return (
    <div className="max-w-2xl mx-auto px-5 py-10">
      <h1 className="font-display text-2xl font-semibold text-kaapi">{pkg.name}</h1>
      <p className="font-mono text-xs text-kaapi/60 mt-1">
        {visited.size} of {pkg.stops.length} stops visited
      </p>

      {errorMessage && <p className="text-verdigris-dark text-sm mt-4">{errorMessage}</p>}

      {activeStop && (
        <div className="mt-6 border-2 border-oxide rounded-md p-5 bg-paper">
          <p className="font-mono text-[11px] tracking-widest text-oxide uppercase mb-1">Now playing</p>
          <h2 className="font-display text-lg font-semibold text-kaapi">{activeStop.name}</h2>
          {activeStop.narrative_text && (
            <p className="text-kaapi/70 text-sm mt-2 leading-relaxed">{activeStop.narrative_text}</p>
          )}
          <audio ref={audioRef} controls className="w-full mt-4" />
        </div>
      )}

      {distanceToNext !== null && visited.size < pkg.stops.length && (
        <p className="text-center font-mono text-xs text-kaapi/50 mt-6">
          ~{Math.round(distanceToNext)} m to next stop
        </p>
      )}

      <ul className="mt-8 flex flex-col divide-y divide-kaapi/10">
        {pkg.stops.map((stop, i) => (
          <li key={stop.id} className="flex items-center gap-3 py-3">
            <span className={`font-mono text-xs w-5 ${visited.has(stop.id) ? 'text-verdigris' : 'text-kaapi/40'}`}>
              {i + 1}
            </span>
            <span className={`text-sm flex-1 ${visited.has(stop.id) ? 'text-verdigris' : 'text-kaapi'}`}>
              {stop.name}
            </span>
            {visited.has(stop.id) && <span className="text-verdigris text-sm">\u2713</span>}
            {!visited.has(stop.id) && (
              <button
                onClick={() => handleArrivedAtStop(stop)}
                className="font-mono text-[10px] text-kaapi/40 underline hover:text-oxide"
              >
                mark manually
              </button>
            )}
          </li>
        ))}
      </ul>

      <Button
        variant="secondary"
        loading={phase === 'finishing'}
        onClick={handleCompleteWalk}
        className="mt-8 w-full"
      >
        End walk now
      </Button>
    </div>
  );
}
