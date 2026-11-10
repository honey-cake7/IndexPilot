import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, LoaderCircle } from "lucide-react";
import { ApiError } from "../api/client";

export const fmt = (v: number | null | undefined, digits = 2) =>
  v == null || !Number.isFinite(v)
    ? "Unknown"
    : v.toLocaleString(undefined, { maximumFractionDigits: digits });
export const bytes = (v: number | null | undefined) =>
  v == null
    ? "Unknown"
    : v < 1024
      ? `${v} B`
      : v < 1048576
        ? `${fmt(v / 1024)} KiB`
        : `${fmt(v / 1048576)} MiB`;
export const short = (v: string) => v.slice(0, 8);
export const date = (v: string) => new Date(v).toLocaleString();
export function PageTitle({
  eyebrow = "WORKLOAD INTELLIGENCE",
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="muted">{description}</p>
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  children,
  className = "",
  action,
}: {
  title?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <div className="panel-heading">
          <h2>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function Busy({ text = "Loading saved evidence…" }: { text?: string }) {
  return (
    <div className="notice" role="status">
      <LoaderCircle className="spin" size={18} />
      {text}
    </div>
  );
}
export function ErrorBox({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  if (!error) return null;
  return (
    <div className="notice error" role="alert">
      <AlertTriangle size={18} />
      <div>
        {error instanceof Error
          ? error.message
          : "The request could not be completed."}
        {error instanceof ApiError && (
          <small>
            {error.code}
            {error.requestId ? ` · Request ${error.requestId}` : ""}
          </small>
        )}
        {retry && (
          <button className="text-button" onClick={retry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function Empty({
  title = "No saved results yet",
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-mark">↗</span>
      <h3>{title}</h3>
      <p className="muted">
        {children ?? (
          <>
            Start with a workload in the{" "}
            <Link to="/analyzer">SQL Analyzer</Link>.
          </>
        )}
      </p>
    </div>
  );
}
export function Tag({
  children,
  tone = "",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={`tag ${tone}`}>{children}</span>;
}
export function Warnings({ items }: { items: string[] }) {
  return items.length ? (
    <details className="warnings">
      <summary>
        {items.length} evidence warning{items.length === 1 ? "" : "s"}
      </summary>
      <ul>
        {items.map((w, i) => (
          <li key={i}>{w}</li>
        ))}
      </ul>
    </details>
  ) : null;
}
export function Metric({
  label,
  value,
  note,
}: {
  label: string;
  value: ReactNode;
  note: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
export function Pager({
  offset,
  count,
  onChange,
  size = 20,
  total,
}: {
  offset: number;
  count: number;
  onChange: (n: number) => void;
  size?: number;
  total?: number;
}) {
  return (
    <div className="pager">
      <span className="muted">
        {count ? `${offset + 1}–${offset + count}` : "No records on this page"}
      </span>
      <button
        className="secondary"
        disabled={offset === 0}
        onClick={() => onChange(Math.max(0, offset - size))}
      >
        Previous
      </button>
      <button
        className="secondary"
        disabled={total === undefined ? count < size : offset + count >= total}
        onClick={() => onChange(offset + size)}
      >
        Next
      </button>
    </div>
  );
}
export function Go({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link className="go" to={to}>
      {children}
      <ArrowRight size={15} />
    </Link>
  );
}
export function Json({
  value,
  title = "Stored evidence JSON",
}: {
  value: unknown;
  title?: string;
}) {
  return (
    <details className="json">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
export function download(name: string, value: unknown, sql = false) {
  const url = URL.createObjectURL(
    new Blob([sql ? String(value) : JSON.stringify(value, null, 2)], {
      type: sql ? "text/plain;charset=utf-8" : "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
