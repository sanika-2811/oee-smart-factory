import { Component, type ErrorInfo, type ReactNode } from 'react'

/** Catches render errors so one broken widget never leaves a blank screen. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error', error, info.componentStack)
  }
  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="card" role="alert" style={{ margin: '40px auto', maxWidth: 560, textAlign: 'center' }}>
        <h2 style={{ marginBottom: 8 }}>Something went wrong on this screen</h2>
        <p className="muted" style={{ marginBottom: 16 }}>The live data connection is not affected. Reload the page, or go back to the overview.</p>
        <div className="row" style={{ justifyContent: 'center' }}>
          <button className="btn primary" onClick={() => window.location.reload()}>Reload</button>
          <a className="btn" href="#/overview" onClick={() => this.setState({ error: null })}>Go to overview</a>
        </div>
      </div>
    )
  }
}
