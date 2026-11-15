import { useEffect, useState, type ReactNode } from "react";
import TeamIcon from "./TeamIcon";
import "./team.css";

type TeamTheme = "light" | "dark";
type TeamPageVariant = "login" | "register" | "portal";

const THEME_KEY = "mrp2026.team.theme";

function readTheme(): TeamTheme {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return stored === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export default function TeamShell({
  children,
  variant,
}: {
  children: ReactNode;
  variant: TeamPageVariant;
}) {
  const [theme, setTheme] = useState<TeamTheme>(readTheme);

  useEffect(() => {
    const syncTheme = (event: StorageEvent) => {
      if (event.key === THEME_KEY || event.key === null) {
        setTheme(readTheme());
      }
    };
    window.addEventListener("storage", syncTheme);
    return () => window.removeEventListener("storage", syncTheme);
  }, []);

  const changeTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    try {
      window.localStorage.setItem(THEME_KEY, nextTheme);
    } catch {
      return;
    }
  };

  return (
    <div
      className={`team-surface team-surface--${variant}`}
      data-team-theme={theme}
    >
      <div className="team-surface__art" aria-hidden="true">
        <svg viewBox="0 0 740 740" fill="none" focusable="false">
          <path d="M670 50c-165 10-308 37-377 118-62 72-7 144 79 165 111 27 171 76 151 168-23 108-200 152-362 189" />
          <path d="M711 119c-151 14-283 32-334 98-48 62 31 91 94 114 127 46 145 126 99 214-45 89-192 137-365 176" />
          <path d="M608 15C461 48 273 77 242 196c-30 116 154 148 218 177 67 30 86 93 25 163-59 66-192 110-346 134" />
        </svg>
      </div>
      <div className="team-shell">
        <header className="team-shell__toolbar">
          <span className="team-shell__mark" aria-hidden="true">
            <TeamIcon name="flag" />
          </span>
          <button
            type="button"
            className="team-theme-toggle"
            onClick={changeTheme}
            aria-label={theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro"}
          >
            <TeamIcon name={theme === "dark" ? "sun" : "moon"} />
            <span>{theme === "dark" ? "Tema claro" : "Tema escuro"}</span>
          </button>
        </header>
        <main className="team-shell__main">{children}</main>
      </div>
    </div>
  );
}
