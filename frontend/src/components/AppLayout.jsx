import { useState } from "react";
import { NavLink, useNavigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { ROLE_LABELS } from "@/lib/api";
import Logo from "@/components/Logo";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import {
  LayoutDashboard, Users, FileText, Pill, ReceiptText,
  ClipboardList, LogOut, FileDown, MessageSquare, Sparkles, Menu,
} from "lucide-react";
import { useEffect } from "react";

const NAV_BY_ROLE = {
  ADMIN: [
    { to: "/admin", label: "Overview", icon: LayoutDashboard, end: true },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/audit", label: "Audit Log", icon: ClipboardList },
    { to: "/admin/cases", label: "All Cases", icon: FileText },
    { to: "/admin/exports", label: "Exports", icon: FileDown },
    { to: "/admin/messaging", label: "Messaging", icon: MessageSquare },
    { to: "/admin/ai", label: "AI Settings", icon: Sparkles },
    { to: "/reception/patients", label: "Patients", icon: Users },
    { to: "/pro/packages", label: "Packages & Dues", icon: ClipboardList },
  ],
  OWNER_DOCTOR: [
    { to: "/doctor", label: "My Queue", icon: LayoutDashboard, end: true },
    { to: "/doctor/all", label: "All Cases", icon: FileText },
    { to: "/doctor/patients", label: "Patients", icon: Users },
    { to: "/doctor/reminders", label: "Reminders", icon: ClipboardList },
    { to: "/pro/packages", label: "Packages & Dues", icon: ClipboardList },
  ],
  DOCTOR: [
    { to: "/doctor", label: "My Queue", icon: LayoutDashboard, end: true },
    { to: "/doctor/patients", label: "My Patients", icon: Users },
    { to: "/pro/packages", label: "Packages & Dues", icon: ClipboardList },
    { to: "/doctor/reminders", label: "Reminders", icon: ClipboardList },
  ],
  RECEPTION: [
    { to: "/reception", label: "Today's Queue", icon: LayoutDashboard, end: true },
    { to: "/reception/patients", label: "Patients", icon: Users },
    { to: "/reception/new-visit", label: "New Visit", icon: FileText },
  ],
  PHARMACY: [
    { to: "/pharmacy", label: "Dashboard", icon: Pill, end: true },
    { to: "/pharmacy/reminders", label: "Reminders", icon: ClipboardList },
  ],
  PRO: [
    { to: "/pro", label: "Billing Queue", icon: ReceiptText, end: true },
    { to: "/pro/packages", label: "Packages & Dues", icon: ClipboardList },
    { to: "/pro/financial-search", label: "Financial Search", icon: Users },
    { to: "/pro/analytics", label: "Analytics", icon: FileText },
  ],
};

function SidebarInner({ user, nav, onLogout, onNavigate }) {
  return (
    <div className="h-full flex flex-col" data-testid="app-sidebar">
      <div className="p-5 border-b border-gray-200">
        <div className="flex items-center gap-3">
          <Logo size={44} />
          <div className="text-[10px] uppercase tracking-[0.18em] text-gray-500 font-semibold leading-tight">
            Internal<br />Workspace
          </div>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto" data-testid="app-nav">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={onNavigate}
            className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            data-testid={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
          >
            <Icon size={18} strokeWidth={1.5} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-gray-200">
        <div className="px-2 py-2 mb-2">
          <div className="text-[11px] uppercase tracking-wider text-gray-500">Signed in</div>
          <div className="font-medium text-sm text-gray-900" data-testid="user-display-name">{user.name}</div>
          <div className="text-xs text-gray-500">{ROLE_LABELS[user.role]}</div>
        </div>
        <button
          onClick={onLogout}
          className="nav-link w-full hover:bg-red-50 hover:text-red-700"
          data-testid="logout-button"
        >
          <LogOut size={18} strokeWidth={1.5} />
          <span>Sign out</span>
        </button>
      </div>
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Close mobile drawer whenever route changes
  useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

  if (!user) return null;
  const nav = NAV_BY_ROLE[user.role] || [];

  const handleLogout = async () => { await logout(); navigate("/login"); };

  return (
    <div className="min-h-screen flex bg-gray-50">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-64 bg-white border-r border-gray-200 flex-col shrink-0">
        <SidebarInner user={user} nav={nav} onLogout={handleLogout} />
      </aside>

      {/* Mobile drawer */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent side="left" className="p-0 w-72 sm:w-80 bg-white">
          <SidebarInner
            user={user}
            nav={nav}
            onLogout={handleLogout}
            onNavigate={() => setDrawerOpen(false)}
          />
        </SheetContent>
      </Sheet>

      {/* Content column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <header
          className="lg:hidden sticky top-0 z-30 bg-white border-b border-gray-200 h-14 flex items-center gap-3 px-3"
          data-testid="mobile-topbar"
        >
          <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
            <SheetTrigger asChild>
              <button
                className="p-2.5 -ml-1 rounded-md hover:bg-gray-100 active:bg-gray-200 touch-manipulation"
                aria-label="Open menu"
                data-testid="mobile-menu-btn"
              >
                <Menu size={22} strokeWidth={1.75} />
              </button>
            </SheetTrigger>
          </Sheet>

          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Logo size={32} />
            <div className="text-[10px] uppercase tracking-[0.18em] text-gray-500 font-semibold truncate">
              {ROLE_LABELS[user.role]}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto" data-testid="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
