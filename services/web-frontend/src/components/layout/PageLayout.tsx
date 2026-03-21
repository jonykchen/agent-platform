import { Outlet } from '@tanstack/react-router';
import { useAuthStore } from '@/stores/authStore';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

interface PageLayoutProps {
  children?: React.ReactNode;
}

export function PageLayout({ children }: PageLayoutProps) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  if (!isAuthenticated) {
    return <>{children || <Outlet />}</>;
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-6">
          {children || <Outlet />}
        </main>
      </div>
    </div>
  );
}

export default PageLayout;