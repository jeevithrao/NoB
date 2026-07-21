import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) return <p className="max-w-2xl mx-auto px-5 py-16 text-kaapi/50 font-mono text-sm">Loading\u2026</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
