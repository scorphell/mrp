/** Rotas do PWA: porta de inscrição pública + portal de equipe + staff. */

import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout";
import { useAuth } from "./auth/AuthContext";
import LoginPage from "./auth/LoginPage";
import ScanPage from "./scan/ScanPage";
import ChecklistPage from "./checklist/ChecklistPage";
import SettingsPage from "./settings/SettingsPage";
import { useTeamAuth } from "./team/TeamAuthContext";
import RegisterPage from "./team/RegisterPage";
import TeamLoginPage from "./team/TeamLoginPage";
import TeamMePage from "./team/TeamMePage";

function RequireAuth({ children }: { children: React.ReactElement }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function RequireTeamAuth({ children }: { children: React.ReactElement }) {
  const { isTeamAuthenticated } = useTeamAuth();
  if (!isTeamAuthenticated) {
    return <Navigate to="/team/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/team/login" element={<TeamLoginPage />} />
        <Route
          path="/me"
          element={
            <RequireTeamAuth>
              <TeamMePage />
            </RequireTeamAuth>
          }
        />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/checklist" element={<ChecklistPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/scan" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
