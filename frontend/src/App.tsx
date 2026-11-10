import { lazy, Suspense, useEffect, useState } from "react";
import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  ChartNoAxesCombined,
  CircleHelp,
  Clock3,
  Database,
  FileChartColumn,
  FlaskConical,
  LayoutDashboard,
  Menu,
  Search,
  SlidersHorizontal,
  Sparkles,
  SquareTerminal,
  X,
} from "lucide-react";
import { api } from "./api/client";
import { Busy, Empty } from "./components/ui";
const Overview = lazy(() =>
  import("./pages/Overview").then((m) => ({ default: m.Overview })),
);
const Connections = lazy(() =>
  import("./pages/Overview").then((m) => ({ default: m.Connections })),
);
const Analyzer = lazy(() =>
  import("./pages/Analyzer").then((m) => ({ default: m.Analyzer })),
);
const Explorer = lazy(() =>
  import("./pages/Explorer").then((m) => ({ default: m.Explorer })),
);
const Budget = lazy(() =>
  import("./pages/Budget").then((m) => ({ default: m.Budget })),
);
const Recommendations = lazy(() =>
  import("./pages/Recommendations").then((m) => ({
    default: m.Recommendations,
  })),
);
const Reports = lazy(() =>
  import("./pages/Reports").then((m) => ({ default: m.Reports })),
);
const Benchmarks = lazy(() =>
  import("./pages/Benchmarks").then((m) => ({ default: m.Benchmarks })),
);
const History = lazy(() =>
  import("./pages/History").then((m) => ({ default: m.History })),
);

const navigation = [
  ["/", "Overview", LayoutDashboard],
  ["/connections", "Connections", Database],
  ["/analyzer", "SQL Analyzer", SquareTerminal],
  ["/queries", "Query Explorer", Search],
  ["/recommendations", "Recommendations", Sparkles],
  ["/budget", "Budget Simulator", SlidersHorizontal],
  ["/benchmarks", "Benchmark Comparison", ChartNoAxesCombined],
  ["/history", "History", Clock3],
  ["/reports", "Reports", FileChartColumn],
] as const;
export function App() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const drawer = document.getElementById("workspace-navigation");
    const links = () =>
      Array.from(drawer?.querySelectorAll<HTMLElement>("a[href],button") ?? []);
    links()[0]?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setOpen(false);
      }
      if (event.key !== "Tab") return;
      const nodes = links();
      const edge = event.shiftKey ? nodes[0] : nodes.at(-1);
      if (document.activeElement === edge) {
        event.preventDefault();
        (event.shiftKey ? nodes.at(-1) : nodes[0])?.focus();
      }
    };
    document.addEventListener("keydown", keyboard);
    return () => {
      document.removeEventListener("keydown", keyboard);
      previous?.focus();
    };
  }, [open]);
  const ready = useQuery({
    queryKey: ["ready"],
    queryFn: api.ready,
    refetchInterval: 30000,
  });
  const location = useLocation();
  const active =
    navigation.find(([path]) => path === location.pathname)?.[1] ??
    "IndexPilot";
  return (
    <>
      <a className="skip" href="#main">
        Skip to content
      </a>
      <div className="app-shell">
        {open && (
          <button
            className="nav-scrim"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
        )}
        <aside
          id="workspace-navigation"
          className={`sidebar ${open ? "is-open" : ""}`}
          role={open ? "dialog" : undefined}
          aria-modal={open || undefined}
          aria-label={open ? "Workspace navigation" : undefined}
        >
          <button
            className="icon-button drawer-close"
            aria-label="Close navigation panel"
            onClick={() => setOpen(false)}
          >
            <X size={18} />
          </button>
          <NavLink className="brand" to="/" onClick={() => setOpen(false)}>
            <span className="brand-icon">
              <Activity size={23} />
            </span>
            IndexPilot<span className="brand-dot">.</span>
          </NavLink>
          <div className="workspace">
            <span className="workspace-icon">
              <Database size={17} />
            </span>
            <div>
              <strong>Local workspace</strong>
              <small>PostgreSQL · demo</small>
            </div>
            <span className="local-dot" />
          </div>
          <p className="nav-label">WORKSPACE</p>
          <nav aria-label="Main navigation">
            {navigation.map(([path, label, Icon]) => (
              <NavLink
                key={path}
                to={path}
                end={path === "/"}
                onClick={() => setOpen(false)}
              >
                <Icon size={18} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="sidebar-note">
              <FlaskConical size={19} />
              <strong>Evidence before action</strong>
              <p>
                Explore hypothetical indexes. Benchmark in an isolated database.
              </p>
            </div>
            <a href="/docs" target="_blank" rel="noreferrer">
              <CircleHelp size={17} />
              API documentation
              <ArrowUpRight size={15} />
            </a>
            <span className="version">IndexPilot / local development</span>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">
              <button
                className="icon-button mobile-menu"
                aria-label={open ? "Close navigation" : "Open navigation"}
                aria-expanded={open}
                onClick={() => setOpen(!open)}
              >
                {open ? <X size={20} /> : <Menu size={20} />}
              </button>
              <span>Workspace</span>
              <span className="slash">/</span>
              <strong>{active}</strong>
            </div>
            <span
              className={`connection-status ${ready.isSuccess ? "online" : ""}`}
            >
              <span />
              {ready.isPending
                ? "Checking API"
                : ready.isError
                  ? "API unavailable"
                  : "API ready"}
              <span className="local-label">LOCAL</span>
            </span>
          </header>
          <main id="main" tabIndex={-1}>
            <Suspense fallback={<Busy />}>
              <Routes>
                <Route path="/" element={<Overview />} />
                <Route path="/connections" element={<Connections />} />
                <Route path="/analyzer" element={<Analyzer />} />
                <Route path="/queries" element={<Explorer />} />
                <Route path="/budget" element={<Budget />} />
                <Route path="/recommendations" element={<Recommendations />} />
                <Route path="/benchmarks" element={<Benchmarks />} />
                <Route path="/history" element={<History />} />
                <Route path="/reports" element={<Reports />} />
                <Route
                  path="*"
                  element={
                    <Empty title="Page not found">
                      Choose a workspace view from the navigation.
                    </Empty>
                  }
                />
              </Routes>
            </Suspense>
          </main>
          <footer>
            PostgreSQL intelligence, with the evidence attached.
            <span>Estimates ≠ measurements</span>
          </footer>
        </div>
      </div>
    </>
  );
}
