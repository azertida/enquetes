// Enquêtes — service worker volontairement vide.
//
// Il ne met RIEN en cache. Son seul rôle est de satisfaire le critère
// d'installabilité de Chrome/Android, qui exige un gestionnaire « fetch ».
//
// Choix délibéré : l'appli n'a aucun intérêt hors ligne (sans enquetes.json
// frais, l'écran est vide ou périmé). Un cache first servirait le programme
// d'il y a trois jours — pire que rien.

self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(clients.claim()));
self.addEventListener('fetch', () => {});
