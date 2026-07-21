import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { Layout } from './components/Layout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { SignupPage } from './pages/SignupPage';
import { TourDetailPage } from './pages/TourDetailPage';
import { WalkPage } from './pages/WalkPage';
import { WalkCompletePage } from './pages/WalkCompletePage';
import { ProfilePage } from './pages/ProfilePage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/tours/:tourId" element={<TourDetailPage />} />
            <Route
              path="/tours/:tourId/walk"
              element={
                <ProtectedRoute>
                  <WalkPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tours/:tourId/complete"
              element={
                <ProtectedRoute>
                  <WalkCompletePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <ProfilePage />
                </ProtectedRoute>
              }
            />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
