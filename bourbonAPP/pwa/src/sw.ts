/// <reference lib="webworker" />
/** Service worker do PWA: precache do app shell + API network-first.
 *
 * O app shell abre offline (troca de endpoint/Nuvem fora) mas chamadas de API
 * nunca vêm do cache de precedência: /api/ usa NetworkFirst com timeout curto
 * para não mascarar um backend indisponível.
 */

import { clientsClaim } from "workbox-core";
import { createHandlerBoundToURL, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { NetworkFirst } from "workbox-strategies";

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

self.skipWaiting();
clientsClaim();

// Lista de arquivos do app shell injetada pelo vite-plugin-pwa no build.
precacheAndRoute(self.__WB_MANIFEST);

// SPA: navegações caem no index.html precacheados.
const appShellHandler = createHandlerBoundToURL("index.html");
const navigationRoute = new NavigationRoute(appShellHandler, {
  denylist: [/^\/api\//],
});
registerRoute(navigationRoute);

// API: network-first, timeout de 3s. Sem cache se a rede falhar.
registerRoute(
  ({ url }) => url.pathname.startsWith("/api/"),
  new NetworkFirst({
    networkTimeoutSeconds: 3,
    cacheName: "checkin-api",
  }),
);

export {};
