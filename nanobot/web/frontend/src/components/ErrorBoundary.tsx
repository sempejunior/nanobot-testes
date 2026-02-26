import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-full bg-background p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-red-muted border border-red/20 flex items-center justify-center mb-6">
            <AlertTriangle className="w-8 h-8 text-red" />
          </div>
          <h2 className="text-lg font-semibold text-text-primary mb-2">
            Something went wrong
          </h2>
          <p className="text-sm text-text-secondary mb-1 max-w-md">
            The interface hit an unexpected error.
          </p>
          <p className="text-xs text-text-muted mb-6 max-w-md font-mono break-all">
            {this.state.error?.message}
          </p>
          <Button onClick={this.handleReset}>
            <RotateCcw className="w-4 h-4 mr-2" />
            Try Again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
