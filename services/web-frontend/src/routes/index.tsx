import { createFileRoute, redirect } from '@tanstack/react-router';

export const Route = createFileRoute('/')({
  component: HomePage,
  beforeLoad: async () => {
    // 重定向到对话页面
    throw redirect({ to: '/chat' });
  },
});

function HomePage() {
  return null;
}

export default Route;