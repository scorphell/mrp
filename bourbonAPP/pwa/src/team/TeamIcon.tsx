type TeamIconName =
  | "flag"
  | "sun"
  | "moon"
  | "arrow"
  | "plus"
  | "qr"
  | "download"
  | "logout"
  | "remove";

export default function TeamIcon({ name }: { name: TeamIconName }) {
  const common = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };

  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      {...common}
    >
      {name === "flag" && (
        <>
          <path d="M5 21V4m0 1.5c2.7-1.4 4.6-1.4 7-.2 2.3 1.2 4.7 1.2 7-.3v12c-2.3 1.5-4.7 1.5-7 .3-2.4-1.2-4.3-1.2-7 .2" />
          <path d="M5 11c2.7-1.4 4.6-1.4 7-.2 2.3 1.2 4.7 1.2 7-.3M12 5.3v12" />
        </>
      )}
      {name === "sun" && (
        <>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
        </>
      )}
      {name === "moon" && (
        <path d="M20.4 15.3A9 9 0 0 1 8.7 3.6 9 9 0 1 0 20.4 15.3Z" />
      )}
      {name === "arrow" && (
        <>
          <path d="M5 12h14m-6-6 6 6-6 6" />
        </>
      )}
      {name === "plus" && <path d="M12 5v14M5 12h14" />}
      {name === "qr" && (
        <>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <path d="M14 14h3v3h-3zm7 0v3h-3m-4 4h3m4-2v2h-2" />
        </>
      )}
      {name === "download" && (
        <>
          <path d="M12 3v12m-4-4 4 4 4-4M4 17v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
        </>
      )}
      {name === "logout" && (
        <>
          <path d="M9 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h4m4-4 5-5-5-5m5 5H9" />
        </>
      )}
      {name === "remove" && <path d="M5 12h14" />}
    </svg>
  );
}
