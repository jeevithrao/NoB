import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="border-b-2 border-kaapi/10 bg-paper/60 backdrop-blur-sm sticky top-0 z-20">
      <div className="max-w-5xl mx-auto px-5 py-4 flex items-center justify-between">
        <Link to="/" className="font-display text-xl font-semibold tracking-tight text-kaapi">
          Neighbourhoods <span className="text-oxide">of Bangalore</span>
        </Link>
        <nav className="flex items-center gap-5 font-body text-sm">
          {user ? (
            <>
              <Link to="/profile" className="text-kaapi/80 hover:text-oxide transition-colors">
                {user.full_name?.split(' ')[0] || 'Profile'}
              </Link>
              <button
                onClick={async () => {
                  await logout();
                  navigate('/login');
                }}
                className="text-verdigris-dark hover:text-verdigris transition-colors"
              >
                Log out
              </button>
            </>
          ) : (
            <Link to="/login" className="text-oxide font-semibold hover:text-oxide-dark transition-colors">
              Log in
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
