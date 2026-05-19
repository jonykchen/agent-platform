import { createRootRoute, Outlet, redirect } from '@tanstack/react-router';
import { useAuthStore } from '@/stores/authStore';

export const Route = createRootRoute({
  component: RootComponent,
  beforeLoad: async ({ location }) => {
    const { isAuthenticated, accessToken } = useAuthStore.getState();

    // 未登录且不在登录页，重定向到登录
    if (!isAuthenticated && !accessToken) {
      if (location.pathname !== '/login' && location.pathname !== '/forbidden') {
        throw redirect({
          to: '/login',
          search: { redirect: location.href },
        });
      }
    }

    // 已登录但在登录页，重定向到首页
    if (isAuthenticated && location.pathname === '/login') {
      throw redirect({ to: '/' });
    }
  },
});

function RootComponent() {
  return <Outlet />;
}

export default Route;