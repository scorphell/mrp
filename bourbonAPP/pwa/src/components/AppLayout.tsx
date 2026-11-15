/** Shell do app: header com saída + navegação inferior (mobile-first). */

import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const NAV_ITEMS = [
  { to: "/scan", label: "Leitura" },
  { to: "/checklist", label: "Checklist" },
  { to: "/settings", label: "Ajustes" },
];

export default function AppLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">MRP2026 · Check-In</span>
        <button
          type="button"
          className="ghost-button"
          onClick={handleLogout}
        >
          Sair
        </button>
      </header>

      <main className="app-main">
        <Outlet />
      </main>

      <nav className="app-nav" aria-label="Navegação principal">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              isActive ? "nav-link active" : "nav-link"
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
