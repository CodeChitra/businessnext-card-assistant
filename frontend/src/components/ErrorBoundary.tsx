import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State {
  failed: boolean
}

/** A render error must never leave the customer looking at a blank page. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('UI error', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="flex h-full items-center justify-center p-8 text-center">
        <div>
          <p className="text-lg">Something went wrong displaying this conversation.</p>
          <button
            type="button"
            className="mt-4 min-h-11 rounded-control bg-teal px-5 font-medium text-on-accent"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </div>
      </div>
    )
  }
}
