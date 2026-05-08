import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, authRequired, loading } = useAuth();
  if (loading) return null;
  if (authRequired && !isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
