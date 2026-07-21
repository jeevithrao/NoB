import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { StampBadge } from '../components/StampBadge';
import { toursApi, purchasesApi, sessionsApi } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import { ApiRequestError } from '../api/client';
import type { CommentOut, TourDetail } from '../api/types';

export function TourDetailPage() {
  const { tourId } = useParams<{ tourId: string }>();
  const { user, deviceId } = useAuth();
  const navigate = useNavigate();

  const [tour, setTour] = useState<TourDetail | null>(null);
  const [comments, setComments] = useState<CommentOut[]>([]);
  const [newComment, setNewComment] = useState('');
  const [liked, setLiked] = useState(false);
  const [ctaLoading, setCtaLoading] = useState(false);
  const [ctaError, setCtaError] = useState('');

  const load = useCallback(async () => {
    if (!tourId) return;
    const [detail, tourComments] = await Promise.all([
      toursApi.get(tourId),
      toursApi.listComments(tourId).catch(() => []),
    ]);
    setTour(detail);
    setComments(tourComments);
  }, [tourId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleToggleLike() {
    if (!tourId) return;
    setLiked((prev) => !prev);
    try {
      const result = liked ? await toursApi.unlike(tourId) : await toursApi.like(tourId);
      setTour((prev) => (prev ? { ...prev, like_count: result.like_count } : prev));
    } catch {
      setLiked((prev) => !prev);
    }
  }

  async function handlePrimaryAction() {
    if (!tour || !tourId) return;
    if (!user) {
      navigate('/login');
      return;
    }

    setCtaError('');
    setCtaLoading(true);
    try {
      if (tour.status === 'not_purchased' && !tour.is_free) {
        await purchasesApi.create(tourId);
        await load();
      } else if (tour.status === 'not_purchased' && tour.is_free) {
        navigate(`/tours/${tourId}/walk`);
      } else if (tour.status === 'purchased') {
        if (tour.purchase_id) {
          await purchasesApi.bindDevice(tour.purchase_id, deviceId);
        }
        navigate(`/tours/${tourId}/walk`);
      } else if (tour.status === 'in_progress') {
        await sessionsApi.createOrResume(tourId);
        navigate(`/tours/${tourId}/walk`);
      }
    } catch (err) {
      setCtaError(err instanceof ApiRequestError ? err.message : 'Something went wrong.');
    } finally {
      setCtaLoading(false);
    }
  }

  async function handleAddComment() {
    if (!tourId || !newComment.trim()) return;
    try {
      const comment = await toursApi.addComment(tourId, newComment.trim());
      setComments((prev) => [comment, ...prev]);
      setNewComment('');
    } catch (err) {
      setCtaError(err instanceof ApiRequestError ? err.message : 'Could not post comment.');
    }
  }

  if (!tour) {
    return <p className="max-w-2xl mx-auto px-5 py-16 text-kaapi/50 font-mono text-sm">Loading\u2026</p>;
  }

  const ctaLabel =
    tour.status === 'not_purchased'
      ? tour.is_free
        ? 'Start free walk'
        : `Buy ticket \u2014 \u20b9${(tour.price_paise / 100).toFixed(0)}`
      : tour.status === 'purchased'
      ? 'Start the walk'
      : tour.status === 'in_progress'
      ? 'Continue walking'
      : 'Walk completed';

  return (
    <div className="max-w-2xl mx-auto px-5 py-10">
      {tour.cover_image && (
        <img src={tour.cover_image} alt="" className="w-full h-56 object-cover rounded-md border-2 border-kaapi/15 mb-6" />
      )}

      <p className="font-mono text-xs tracking-widest text-kaapi/50 uppercase mb-2">{tour.city}</p>
      <h1 className="font-display text-3xl font-semibold text-kaapi leading-tight">{tour.name}</h1>

      <div className="flex items-center gap-3 mt-4">
        <StampBadge status={tour.status} />
        <span className="font-mono text-xs text-kaapi/60">
          {tour.duration_min} min \u00b7 {tour.distance_km} km \u00b7 {tour.stop_count} stops
        </span>
      </div>

      <p className="font-body text-kaapi/80 leading-relaxed mt-6">{tour.description}</p>

      {ctaError && <p className="text-verdigris-dark text-sm mt-4">{ctaError}</p>}

      <div className="flex gap-3 mt-6">
        <Button onClick={handlePrimaryAction} loading={ctaLoading} disabled={tour.status === 'completed_locked'}>
          {ctaLabel}
        </Button>
        <Button variant="secondary" onClick={handleToggleLike}>
          {liked ? '\u2665 Liked' : '\u2661 Like'} \u00b7 {tour.like_count}
        </Button>
      </div>

      <hr className="border-kaapi/10 my-10" />

      <h2 className="font-display text-xl font-semibold text-kaapi mb-4">Comments</h2>
      {tour.status === 'completed_locked' ? (
        <div className="flex gap-2 mb-6">
          <input
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
            placeholder="Share how the walk went\u2026"
            className="flex-1 border-2 border-kaapi/15 rounded-md px-4 py-2 bg-paper focus:border-oxide outline-none font-body text-sm"
          />
          <Button onClick={handleAddComment}>Post</Button>
        </div>
      ) : (
        <p className="text-kaapi/50 text-sm mb-6 font-mono">Finish walking this tour to leave a comment.</p>
      )}

      <div className="flex flex-col gap-4">
        {comments.map((c) => (
          <div key={c.id} className="border-t border-kaapi/10 pt-3">
            <p className="font-semibold text-oxide text-sm">{c.user_name || 'A walker'}</p>
            <p className="text-kaapi/80 text-sm mt-1">{c.content}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
