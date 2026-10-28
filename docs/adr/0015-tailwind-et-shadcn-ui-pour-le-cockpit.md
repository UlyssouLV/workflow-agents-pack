# 0015 — Tailwind et shadcn/ui pour le cockpit

- Statut : accepté
- Date : 2026-10-28
- Version : 0.8.1 (#123)

## Contexte

Depuis la 0.3.0, le cockpit est stylé par une seule feuille `style.css` écrite à la main (« style minimal », le design était hors périmètre) : couleurs en dur, aucune variable, aucun composant partagé ; chaque version a ajouté ses classes. La 0.8.1 redessine tout le cockpit sous l’identité HéphaïstOS (maquette validée : `docs/specs/v0.8.1-maquette-cockpit.html`, direction Atelier). Il faut une boîte de dialogue modale (clone sale, Terminer), des onglets, un panneau coulissant sur téléphone, des infobulles, un interrupteur, un repliable et des toasts, tous accessibles (focus piégé, Échap, ARIA). Alternatives : CSS pur avec variables ; bibliothèque de composants packagée (MUI, Mantine…) ; Tailwind et shadcn/ui, déjà retenus par ArgOS (son ADR 0016).

## Décision

1. **Tailwind v4** (`@tailwindcss/vite`) et **shadcn/ui** : composants copiés dans `orchestrator/cockpit/src/components/ui/`, au-dessus de **Radix**, avec lucide-react (icônes), sonner (toasts), `class-variance-authority`, `clsx`, `tailwind-merge`. Même technique qu’ArgOS, identité propre.
2. **Identité dans des variables CSS** sur `:root` (couleurs, rayons, polices), exposées à Tailwind par `@theme inline`. Thème sombre uniquement. Code couleur des états unique : attention (orange), agent (bleu), pilote (violet), succès, échec, neutre.
3. **Polices embarquées** (Geist, Geist Mono, woff2 sous licence OFL) : aucune requête vers un CDN, une instance lue par tunnel peut n’avoir aucun accès Internet.
4. **xterm.js et Monaco** reçoivent des thèmes construits à partir des mêmes valeurs.
5. Les **nouvelles** dépendances sont épinglées à la version exacte ; les `^` existantes ne changent pas dans cette version.

## Conséquences

- `style.css` disparaît ; toute UI utilise `components/ui/` et les variables, pas de couleur ni de taille en dur hors des variables.
- Les tests du cockpit visent rôles et libellés, jamais des classes Tailwind.
- Un composant shadcn/ui ajouté plus tard est copié puis versionné comme du code du dépôt ; ses dépendances Radix sont épinglées à la version exacte.
- Les `<select>` restent natifs (stylés), l’arbre du codespace reste un arbre ARIA maison : Radix n’apporte rien de mieux pour eux.
- Un thème clair plus tard ne demandera qu’un second jeu de variables.
- Le build du cockpit gagne Tailwind (CSS purgé à la compilation, coût négligeable).
