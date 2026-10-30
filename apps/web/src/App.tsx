import { lazy, Suspense, useEffect, useState } from 'react'
import {
  BrowserRouter,
  Link,
  NavLink,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router'
import {
  Activity,
  ArrowUpRight,
  ChevronRight,
  FolderKanban,
  LayoutDashboard,
  LockKeyhole,
  Radio,
  Search,
  X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NoticeContext } from '@/lib/notice'
import { useSession } from '@/lib/api'
import { EmptyPanel, LoadingPanel } from '@/components/workspace'

const DashboardPage = lazy(() =>
  import('@/pages/operations').then((module) => ({
    default: module.DashboardPage,
  })),
)
const CaseListPage = lazy(() =>
  import('@/pages/operations').then((module) => ({
    default: module.CaseListPage,
  })),
)
const AlertListPage = lazy(() =>
  import('@/pages/operations').then((module) => ({
    default: module.AlertListPage,
  })),
)
const AlertDetailPage = lazy(() =>
  import('@/pages/operations').then((module) => ({
    default: module.AlertDetailPage,
  })),
)
const CasePage = lazy(() =>
  import('@/pages/case-workspace').then((module) => ({
    default: module.CasePage,
  })),
)
const SystemPage = lazy(() =>
  import('@/pages/system').then((module) => ({ default: module.SystemPage })),
)

const navigation = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/cases', label: 'Cases', icon: FolderKanban },
  { to: '/alerts', label: 'Alerts', icon: Radio },
  { to: '/system', label: 'System', icon: Activity },
]

function WorkspaceShell() {
  const location = useLocation()
  const navigate = useNavigate()
  const session = useSession()
  const [notice, setNotice] = useState('')
  const section = location.pathname.startsWith('/cases')
    ? 'Cases'
    : location.pathname.startsWith('/alerts')
      ? 'Alerts'
      : location.pathname === '/system'
        ? 'System'
        : 'Overview'
  useEffect(() => {
    document.title = `${section} · ATÉ`
    window.scrollTo(0, 0)
  }, [section, location.pathname])
  useEffect(() => {
    if (!notice) return
    const timer = setTimeout(() => setNotice(''), 9000)
    return () => clearTimeout(timer)
  }, [notice])
  return (
    <NoticeContext value={setNotice}>
      <div className="workspace-shell">
        <a href="#main" className="skip-link">
          Skip to content
        </a>
        <aside className="sidebar">
          <Link to="/" className="brand" aria-label="ATÉ overview">
            <span className="brand-symbol">
              <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
                <path
                  d="M5 25 15.8 6 27 25h-7.1l-4.1-7-4 7H5Z"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinejoin="round"
                />
                <path
                  d="M12 14h15M9 19h13"
                  stroke="currentColor"
                  strokeWidth="1.7"
                />
              </svg>
            </span>
            <span className="brand-name">
              ATÉ<span className="brand-subtitle">SECURITY OPERATIONS</span>
            </span>
            <span className="brand-tag">SOC</span>
          </Link>
          <div className="sidebar-workspace">
            <span className="workspace-indicator" />
            <div>
              <p>Analyst workspace</p>
              <span>Local development</span>
            </div>
            <LockKeyhole
              className="ml-auto size-3.5 text-muted-foreground"
              aria-hidden="true"
            />
          </div>
          <p className="nav-label">OPERATIONS</p>
          <nav aria-label="Workspace" className="workspace-nav">
            {navigation.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `nav-item ${isActive ? 'nav-active' : ''}`
                }
              >
                <Icon className="size-[17px]" aria-hidden="true" />
                <span>{label}</span>
                <ChevronRight
                  className="nav-arrow ml-auto size-3.5"
                  aria-hidden="true"
                />
              </NavLink>
            ))}
          </nav>
          <div className="sidebar-footer">
            <div className="operator-mark">
              <span />
              <span />
              <span />
              <span />
            </div>
            <p>
              Evidence first.
              <br />
              <strong>Analyst in control.</strong>
            </p>
            <div className="sidebar-footer-line">
              <span className="size-1.5 rounded-full bg-primary" />
              SELF-HOSTED WORKSPACE
            </div>
            <a
              href="/docs"
              target="_blank"
              rel="noreferrer"
              className="api-reference"
            >
              API reference
              <ArrowUpRight className="size-3.5" aria-hidden="true" />
            </a>
          </div>
        </aside>
        <div className="workspace-body">
          <header className="workspace-header">
            <div className="breadcrumbs">
              <span>Workspace</span>
              <ChevronRight className="size-3" aria-hidden="true" />
              <span className="text-foreground">{section}</span>
            </div>
            <form
              className="global-search"
              role="search"
              onSubmit={(event) => {
                event.preventDefault()
                const value = String(
                  new FormData(event.currentTarget).get('q') ?? '',
                )
                void navigate(`/cases?q=${encodeURIComponent(value)}`)
              }}
            >
              <Search className="size-3.5" aria-hidden="true" />
              <Input
                aria-label="Search cases across workspace"
                name="q"
                maxLength={200}
                placeholder="Search cases…"
              />
              <span>CASES</span>
            </form>
            <div className="analyst-profile">
              <div className="profile-avatar">LA</div>
              <div>
                <p>{session.data?.actor.handle ?? 'Local workspace'}</p>
                <span>{session.data ? 'Local analyst' : 'Connecting'}</span>
              </div>
            </div>
          </header>
          <main id="main" className="workspace-main" tabIndex={-1}>
            {notice && (
              <div role="status" className="success-notice">
                <span className="size-1.5 rounded-full bg-primary" />
                {notice}
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="ml-auto shrink-0"
                  aria-label="Dismiss notification"
                  onClick={() => setNotice('')}
                >
                  <X />
                </Button>
              </div>
            )}
            <Suspense fallback={<LoadingPanel message="Opening workspace" />}>
              <Outlet />
            </Suspense>
          </main>
          <footer className="workspace-footer">
            <span>
              <span className="size-1.5 rounded-full bg-primary" />
              ATÉ / ANALYST WORKSPACE
            </span>
            <span>HUMAN-REVIEWED DECISIONS</span>
          </footer>
        </div>
      </div>
    </NoticeContext>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<WorkspaceShell />}>
          <Route index element={<DashboardPage />} />
          <Route path="cases" element={<CaseListPage />} />
          <Route path="cases/:id" element={<CasePage />} />
          <Route path="alerts" element={<AlertListPage />} />
          <Route path="alerts/:id" element={<AlertDetailPage />} />
          <Route path="system" element={<SystemPage />} />
          <Route
            path="*"
            element={
              <EmptyPanel
                title="Page not found"
                description="Choose a workspace section to continue."
              >
                <Button asChild>
                  <Link to="/">Return to overview</Link>
                </Button>
              </EmptyPanel>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
