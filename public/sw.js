// Service worker minimo para tr-bot.
// Unico proposito: permitir que el navegador ofrezca "Agregar a pantalla de inicio".
// No cachea nada ni intercepta peticiones (sin funcionalidad offline).

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    self.clients.claim();
});

// Sin listener de 'fetch': todas las peticiones van directo a la red,
// el navegador maneja todo como si el service worker no existiera
// excepto para el criterio de instalabilidad.
