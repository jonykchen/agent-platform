import { createFileRoute } from '@tanstack/react-router';
import { Result, Button } from 'antd';
import { usePermission } from '@/hooks/usePermission';

export const Route = createFileRoute('/forbidden')({
  component: ForbiddenPage,
});

function ForbiddenPage() {
  const { isAdmin } = usePermission();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Result
        status="403"
        title="无访问权限"
        subTitle="您没有权限访问此页面，请联系管理员"
        extra={[
          <Button key="home" onClick={() => window.location.href = '/'}>
            返回首页
          </Button>,
          isAdmin && (
            <Button key="back" onClick={() => window.history.back()}>
              返回上一页
            </Button>
          ),
        ].filter(Boolean)}
      />
    </div>
  );
}

export default Route;