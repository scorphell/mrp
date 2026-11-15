import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import App from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { TeamAuthProvider } from "./team/TeamAuthContext";
import "./styles.css";

// Registra o service worker (precache do app shell; API nunca é precacheadas).
registerSW({ immediate: true });

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuthProvider>
      <TeamAuthProvider>
        <App />
      </TeamAuthProvider>
    </AuthProvider>
  </StrictMode>,
);
