import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { toursApi } from '../api/endpoints';
import { ApiRequestError } from '../api/client';

export function WalkCompletePage() {
  const { tourId } = useParams<{ tourId: string }>();
  const navigate = useNavigate();
  const [comment, setComment] = useState('');
  const [posted, setPosted] = useState(false);
  const [posting, setPosting] = useState(false);
  const [error, setError] = useState('');

  async function handlePost() {
    if (!tourId || !comment.trim()) return;
    setPosting(true);
    try {
      await toursApi.addComment(tourId, comment.trim());
      setPosted(true);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Could not post your comment.');
    } finally {
      setPosting(false);
    }
  }

  return (
    <div className="max-w-md mx-auto px-5 py-20 text-center">
      <p className="stamp inline-block border-2 border-verdigris text-verdigris rounded-sm px-4 py-1 font-mono text-sm tracking-widest uppercase mb-6">
        Ticket punched
      </p>
      <h1 className="font-display text-3xl font-semibold text-kaapi">Walk complete</h1>
      <p className="text-kaapi/70 mt-4 leading-relaxed">
        This tour\u2019s pass is now used \u2014 buy a fresh ticket any time you want to walk it again.
      </p>

      {!posted ? (
        <div className="mt-8 flex flex-col gap-3">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="How was the walk?"
            rows={3}
            className="border-2 border-kaapi/15 rounded-md px-4 py-3 bg-paper focus:border-oxide outline-none font-body text-sm"
          />
          {error && <p className="text-verdigris-dark text-sm">{error}</p>}
          <Button onClick={handlePost} loading={posting}>
            Post comment
          </Button>
        </div>
      ) : (
        <p className="text-verdigris mt-8 font-body">Thanks for sharing!</p>
      )}

      <Button variant="secondary" className="mt-6 w-full" onClick={() => navigate('/')}>
        Back to tours
      </Button>
    </div>
  );
}
