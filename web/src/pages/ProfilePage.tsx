import { useNavigate } from 'react-router-dom';
import { Button } from '../components/Button';
import { useAuth } from '../context/AuthContext';

export function ProfilePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="max-w-md mx-auto px-5 py-16">
      <h1 className="font-display text-2xl font-semibold text-kaapi">{user?.full_name || 'Wanderer'}</h1>
      <p className="text-kaapi/60 mt-1 font-mono text-sm">{user?.email}</p>

      <Button
        variant="danger"
        className="mt-8 w-full"
        onClick={async () => {
          await logout();
          navigate('/login');
        }}
      >
        Log out
      </Button>
    </div>
  );
}
