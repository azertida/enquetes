# Enquêtes

Application web installable (PWA) qui recense les **séries policières et
téléfilms du terroir franco-belges** diffusés sur sept jours, sur six chaînes
généralistes : TF1, France 2, France 3, TV5 Monde, La Une et Tipik.

Aucun serveur, aucun compte, aucune donnée collectée. Les données sont
regénérées automatiquement par GitHub Actions et servies en fichier statique.

---

## Comment un programme est détecté

Deux mécanismes tournent **en parallèle**. Un programme est retenu s'il
satisfait l'un **ou** l'autre.

### 1. La liste blanche — `series.json`

Elle couvre les **séries récurrentes**, dont le titre est stable et connu
d'avance : Capitaine Marleau, Alex Hugo, HPI, Munch…

La comparaison se fait par **préfixe normalisé** : casse, accents,
apostrophes typographiques et espaces multiples sont ignorés, et le test
porte sur le titre **comme sur le sous-titre** Pickx.

Cela absorbe les variantes d'une source à l'autre :

| Écrit par Pickx                    | Reconnu comme |
| ---------------------------------- | ------------- |
| `Leo Mattéi, brigades des mineurs` | Léo Mattéi    |
| `LEO MATTEI` + sous-titre          | Léo Mattéi    |
| `Munch : Le Silence`               | Munch         |
| `Edvard Munch, la danse de la vie` | *(rejeté)*    |

**Règle d'écriture** : inscrire le **préfixe le plus court qui reste sans
ambiguïté**. `Léo Mattéi` suffit — tout ce qui suit la virgule varie selon
les sources. Mais `Commissaire Magellan` doit rester entier : réduit à
`Magellan`, il attraperait les documentaires sur le navigateur.

Pour retirer une série sans perdre l'entrée : `"actif": false`.

### 2. Le motif « téléfilm du terroir »

Il couvre les **inédits**, dont le titre est imprévisible mais la *forme*
reconnaissable : `mot-clé + préposition + lieu propre`.

`Meurtres à Sarlat`, `Crimes au mont Ventoux`, `Mystères en Balagne`…

Aucune liste à tenir : un téléfilm diffusé pour la première fois demain est
capté sans intervention.

---

## Limite assumée

Un téléfilm inédit dont le titre ne suit **ni** la liste blanche **ni** le
motif échappe aux deux mécanismes. *Les Bois hantés* en est un bon exemple :
ni mot-clé, ni préposition, ni lieu propre.

Élargir les mots-clés (*Disparition*, *Affaire*, *Traque*…) capterait ces
cas, mais au prix de faux positifs nombreux — documentaires animaliers,
magazines d'actualité. **C'est le bruit qui fait désinstaller une appli, pas
l'oubli.** Le choix est donc de rater quelques titres et de l'annoncer
clairement aux utilisateurs plutôt que de noyer la liste.

Un correctif reste possible au cas par cas : ajouter le titre manqué à
`series.json`.

---

## Fonctionnement technique

```
iptv-org/epg (grabber Pickx)
        ↓  XML local
   enquetes.py  ←  series.json
        ↓
   enquetes.json
        ↓  fetch + cache-busting
     index.html
```

* `enquetes.py` — Python, bibliothèque standard uniquement, aucune dépendance.
* Déduplication sur `(titre, début, chaîne)` : Pickx répète chaque programme
  sur ses variantes HD / SD / +1.
* Le service worker est **volontairement vide** : aucun cache. L'appli n'a
  aucun intérêt hors ligne, et un cache servirait un programme périmé. Il
  n'existe que pour satisfaire le critère d'installabilité de Chrome.

### Exécution locale

```bash
python3 enquetes.py --source=/chemin/vers/pickx_guide.xml
```

Options : `--series` pour pointer une autre liste blanche, `--no-filter`
pour désactiver tout filtrage (débogage).

### Journal d'exécution

Chaque exécution affiche, en fin de sortie, les entrées de `series.json`
**sans diffusion sur la fenêtre**. Utile le jour où une série paraît
absente : la réponse est déjà dans le log GitHub Actions.

---

## Fichiers

| Fichier             | Rôle                                        |
| ------------------- | ------------------------------------------- |
| `enquetes.py`       | Collecte et filtrage                        |
| `series.json`       | Liste blanche des séries                    |
| `enquetes.json`     | Données générées *(ne pas éditer)*          |
| `index.html`        | Interface, fichier unique                   |
| `manifest.json`     | Installation Android                        |
| `service-worker.js` | Installabilité Chrome, sans cache           |
| `icon*.png`         | Icônes                                      |

---

## Licence

CC0 — domaine public.
