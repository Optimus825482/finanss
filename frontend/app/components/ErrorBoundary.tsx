"use client";

import React, { Component, ReactNode } from "react";

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { hasError: boolean; message: string };

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message || "Bilinmeyen hata" };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, message: "" });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div
          className="rounded-sm p-6 m-4 font-mono text-sm"
          style={{
            backgroundColor: "rgba(220, 38, 38, 0.1)",
            color: "var(--term-red)",
            border: "1px solid var(--term-red)",
          }}
        >
          <div className="text-[11px] tracking-[0.2em] mb-2">BİLEŞEN HATASI</div>
          <p className="mb-3">{this.state.message}</p>
          <button
            onClick={this.handleReset}
            className="px-4 py-2 rounded-sm text-xs tracking-wider"
            style={{ border: "1px solid var(--term-red)", color: "var(--term-red)" }}
          >
            ↻ TEKRAR DENE
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
