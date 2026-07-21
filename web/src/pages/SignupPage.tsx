import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useAuth } from '../context/AuthContext';
import { ApiRequestError } from '../api/client';

export function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await signup(email.trim(), password, fullName.trim());
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center px-5">
      <div className="w-full max-w-sm">
        <h1 className="font-display text-3xl font-semibold text-center text-kaapi">Create your account</h1>
        <p className="text-center text-kaapi/60 text-sm mt-2 mb-8">First walk\u2019s on us \u2014 Cubbon Park is free.</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            required
            placeholder="Full name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="border-2 border-kaapi/15 rounded-md px-4 py-3 bg-paper focus:border-oxide outline-none font-body"
          />
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="border-2 border-kaapi/15 rounded-md px-4 py-3 bg-paper focus:border-oxide outline-none font-body"
          />
          <input
            type="password"
            required
            placeholder="Password (min 8 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="border-2 border-kaapi/15 rounded-md px-4 py-3 bg-paper focus:border-oxide outline-none font-body"
          />
          {error && <p className="text-verdigris-dark text-sm">{error}</p>}
          <Button type="submit" loading={loading} className="w-full mt-2">
            Sign up
          </Button>
        </form>

        <p className="text-center text-sm text-kaapi/60 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-oxide font-semibold">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
