import { Component, ErrorInfo, ReactNode } from 'react';
import { Button, Result } from 'antd';
import * as Sentry from '@sentry/react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  eventId?: string;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const eventId = Sentry.captureException(error, {
      contexts: {
        react: {
          componentStack: errorInfo.componentStack,
        },
      },
      tags: {
        route: window.location.pathname,
      },
    });

    this.setState({ eventId });
    console.error('ErrorBoundary caught:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-screen p-8">
          <Result
            status="error"
            title="出现错误"
            subTitle={this.state.error?.message || '未知错误'}
            extra={[
              <Button
                key="feedback"
                onClick={() =>
                  Sentry.showReportDialog({ eventId: this.state.eventId })
                }
              >
                反馈问题
              </Button>,
              <Button
                key="reload"
                type="primary"
                onClick={() => window.location.reload()}
              >
                刷新页面
              </Button>,
            ]}
          />
          {this.state.eventId && (
            <p className="text-xs text-gray-400">
              错误追踪 ID: {this.state.eventId}
            </p>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;