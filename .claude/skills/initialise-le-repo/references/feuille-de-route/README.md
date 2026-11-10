# Feuille de route de dev — standards

Source unique : **`feuille-de-route-dev.md`**.

Outils branchés dessus :

- skill `/afr` (`augmenter-la-feuille-de-route-dev`) — rôle `roadmap` dans `agents/roles.yml` ;
- skill `/cub` (`creer-un-bug`) — issue GitHub `bug` + entrée sous **Plus tard** ;
- opt-in **blocages** (voir *Blocages*) : skill `/dfr` (`debloquer-la-feuille-de-route`) et le script du projet `scripts/deblocages-feuille-de-route.mjs` ;
- si le rôle **`docs-site`** est activé (opt-in `/init` ou `update-from-pack.sh --with-docs`) : `docs-site/scripts/generer-feuille-de-route.mjs` et `generer-bugs.mjs` au build Pages.

Ce n’est **pas** une spec (la spec naît à « Ouvre la version »).

## Structure du fichier

```text
# Feuille de route de dev
## Déjà livré          ← puces **X.Y.Z** — titre + résumé court
## Prochaine : X.Y.Z — Titre
## Ensuite : X.Y.Z — Titre   (répétable)
## Plus tard (pas encore numéroté)
### … sujets / bugs …
```

| Section | Rôle |
| --- | --- |
| **Déjà livré** | Versions shipped (une puce par `X.Y.Z`). |
| **Prochaine** | Exactement **une** version : la suivante à ouvrir. Avec les blocages : **au plus une**, la **première ouvrable**, calculée. |
| **Ensuite** | Versions numérotées après la Prochaine, dans l’ordre. Avec les blocages : toutes les autres, ouvrables ou bloquées, dans l’ordre des numéros. |
| **Plus tard** | Idées / bugs **sans** semver encore (ou reprise plus tard). |

À « Finalise la version » : la version livrée passe en **Déjà livré** ; la première **Ensuite** devient **Prochaine** (avec les blocages : **`/dfr`** recalcule les états et la Prochaine).

## Conventions d’écriture des versions

### Numérotation

- Semver : `X.Y.Z` (ex. `1.4.4`, `1.5.0`) — c’est le **numéro de développement** (voir ci-dessous).
- Titre de section : `## Prochaine : X.Y.Z — <titre>` ou `## Ensuite : X.Y.Z — <titre>`.
- Un **seul job** par version (un objectif métier clair).

### Numéro de développement et numéro produit

Deux suivis. Tant que les versions arrivent sur `main` dans l’ordre de leurs numéros, les deux sont égaux et rien ne change.

| | Numéro de développement | Numéro produit |
| --- | --- | --- |
| Où | ce fichier, specs, branches `vX.Y.Z-…`, issues, PR, commits, suivi d’avancement | tag et titre de la GitHub Release, version affichée par le produit, site de doc |
| Ordre | par thème ; deux séries peuvent arriver sur `main` en alternance | **toujours croissant**, dans l’ordre d’arrivée sur `main` |
| Fixé | à l’ouverture de la version | à « Finalise la version » |

Sens des chiffres (communs aux deux suivis) :

- **majeur** — rupture qui demande un geste à tous (réinstaller, migrer des données à la main, mise en production définitive) ; décidé dans ce fichier, jamais calculé ;
- **mineur** — une **série** = un grand thème ;
- **correctif** — une étape de plus dans la série, une correction, ou une version arrivée après une série plus récente.

À « Finalise la version », le numéro produit se calcule ainsi :

1. **Rien de livré à l’utilisateur final** — seulement si le rôle optionnel **`livrables`** existe dans `agents/roles.yml` (ce qui entre dans ce que l’utilisateur installe : images, paquets, sources de l’application) : le diff de la branche (`origin/main...HEAD`) ne touche aucun de ces chemins, hors tests et fichiers `.md` → **pas de Release**, donc pas de numéro produit. La version passe en **Déjà livré** sous son numéro de développement ; le site de doc se publie à la fusion.
2. **Numéro de développement plus grand que la dernière Release** (comparaison semver) → numéro produit = numéro de développement.
3. **Sinon** → numéro produit = dernière Release, correctif + 1.

Titre de la Release : `VX.Y.Z — <titre>` au numéro produit ; le numéro de développement figure dans ses notes (`Développement : A.B.C (#<parent>)`).

Exemples : développement 1.5.2 finalisée après la Release 1.6.2 → produit **1.6.3** ; une série de documentation sans `livrables` touchés → aucune Release ; 1.8.0 après 1.6.3 → **1.8.0** ; une 1.8.3 finalisée après la Release 1.9.0 → **1.9.1**.

Sur le site de doc, le Changelog montre le numéro produit. Une version à venir n’en a pas encore : quand le rôle `livrables` existe, la feuille de route du site la présente par son titre, sans numéro ; elle passe au Changelog une fois livrée.

Dans **Déjà livré**, la puce garde le numéro de développement et indique le numéro produit quand il diffère (`**1.5.2** — … Livrée en **1.6.3**.`) ou l’absence de Release (`Sans Release produit.`).

### Corps d’une version (Prochaine / Ensuite)

- **`Objectif.`** — ce que l’utilisateur / collaborateur gagne (langage produit).
- **`Hors périmètre`** — ce qui est explicitement reporté (souvent vers une autre version).
- Optionnel : auth / orientation technique / recherche / tests, si utile avant le grilling.
- Pas de détail d’implémentation digne d’une spec ; les décisions figées peuvent pointer vers un ADR ou une issue.

### Blocages (opt-in)

Seulement quand le projet a **`scripts/deblocages-feuille-de-route.mjs`** (script du projet, appelé par son script d’avancement). Sans lui, rien de cette section ne s’applique.

Chaque version (Prochaine / Ensuite) porte alors, dans cet ordre : **`État.`** juste sous le titre (**calculé** par le script, jamais écrit ni fusionné à la main), **`Objectif.`**, **`Bloquée par.`** (**toujours présente**), optionnellement **`À trancher au grilling.`**, puis **`Hors périmètre`**.

Une version est **bloquée** par une autre quand une partie de son **Objectif** ne peut pas se faire sans elle. Écrit par **`/afr`** à la création de la version, revu quand un objectif change.

```markdown
**Bloquée par.**

- **1.5.0** — les crédits initiaux qu’un participant reçoit à l’inscription n’existent pas encore.
- **1.4.2** — la borne refuse au-delà du débit maximal.
```

- Une puce par version **directement** nécessaire : `- **X.Y.Z** — raison`, la raison en langage produit (ce qui manque, pas une table ou une route). Les blocages hérités ne se recopient pas.
- Le numéro cité est une version de **Déjà livré**, de **Prochaine** ou d’**Ensuite** ; pas de cycle. Le script refuse sinon.
- Une version qui ne dépend de rien : `**Bloquée par.** Aucune.`
- **Levée = fusionnée sur la base.** Un bloqueur est levé quand sa version est dans **Déjà livré**. Une version ouverte, ou dont la PR est prête, ne débloque rien : ne pas ouvrir une version depuis la branche d’une autre (le squash-merge réécrit ses commits).
- **Pas de blocage partiel.** Un bloqueur bloque toute la version. S’il ne touche qu’une partie de l’objectif, on **découpe** avec **`/afr`** : la partie bloquée passe en **Hors périmètre** vers la version qui bloque (si elle y a sa place) ou vers une nouvelle version, et la version perd ce bloqueur. **`/dfr`** signale ces cas, il ne les tranche pas.

**`État.`** se déduit des bloqueurs et de **Déjà livré** :

| État | Quand | Ligne écrite |
| --- | --- | --- |
| Ouvrable | tous ses bloqueurs sont livrés | `**État.** Ouvrable.` |
| Bloquée | il reste au moins un bloqueur | `**État.** Bloquée : il reste **1.6.1**.` ; `(n sur m)` quand une partie est déjà levée |

La **Prochaine** est la première version ouvrable dans l’ordre du fichier ; aucune si tout est bloqué. « Ouvre la version » sans numéro prend la première ouvrable **pas encore en cours**.

« En cours » (branche `vX.Y.Z-…` ou PR ouverte) n’est **pas** écrit : une branche non fusionnée est invisible depuis la base. **`/dfr`** et « Ouvre la version » le lisent sur GitHub.

**Versions en parallèle.** Plusieurs versions ouvrables peuvent être ouvertes en même temps. Chacune, fusionnée, débloque ce qui l’attendait, dans l’ordre d’arrivée sur la base. Deux branches qui modifient la feuille se réconcilient en relançant le script après fusion de la base : **État.**, **Prochaine** et le bandeau du README (si le projet en a un) ne se fusionnent jamais à la main. La copie d’une branche peut dater ; celle de la base fait foi.

### Déjà livré

- Une ligne : `**X.Y.Z** — titre : résumé…` avec liens utiles (`#issue`, spec, ADR) si déjà connus.
- Bug connu **livré avec** la version : le mentionner ici **et** le reporter en **Plus tard** / Bug tant qu’il n’est pas corrigé.

## Bugs

Création standardisée : skill **`/cub`** (`creer-un-bug`) — issue GitHub **et** entrée feuille. Ne pas inventer un format parallèle.

Les bugs non encore numérotés en version vivent sous **`## Plus tard (pas encore numéroté)`**.

### Titre

```markdown
### Bug — <description courte> (#n)
```

- Préfixe **`Bug —`** obligatoire (repérable, distinct d’une idée produit).
- Lien issue GitHub (`#n`) dès qu’elle existe ; label **`bug`** côté tracker (pas `ready-for-agent`).
- Titre d’issue = même libellé : `Bug — <description courte>`.
- Nouvel bug → **`/cub`** (crée l’issue puis écrit la feuille). Pas d’entrée feuille sans `#n` pour un bug nouveau.
- **Captures** (si fournies) → pièces jointes GitHub via `gh issue create|edit --attach` (voir `agents/issue-tracker.md` *Bugs*). Sur la feuille : renvoyer vers l’issue, ne pas coller les binaires.

### Corps (feuille **et** issue — mêmes titres)

Ordre fixe — **chaque** rubrique est toujours présente :

1. **Constat** — ce qui a été vu.
2. **Reproductibilité** — étapes / conditions ; ou `Non déterminé` (on a cherché, pas reproductible clairement) ; ou jeton ci-dessous.
3. **Impact** — qui / quoi est cassé.
4. **Cause probable** — hypothèse ; ou `Inconnue` (examiné, pas d’hypothèse) ; ou jeton ci-dessous.
5. **À corriger** — intention produit (pas le patch).
6. **Hors périmètre** — ou `Aucun.`
7. **Métadonnées** (issue) / **Suivi** (feuille) :
   - Trouvé dans : `X.Y.Z` \| `inconnu` \| jeton
   - Contexte : `test humain` \| `usage` \| `revue` \| … \| jeton
   - Date : `YYYY-MM-DD` \| jeton
   - Priorité : `bloquant` \| `avant déploiement` \| `non prioritaire` \| jeton
   - Sur la feuille : lien `[#n](url)` (`bug`) + les mêmes puces / ligne Suivi.

#### Jeton `Informations manquantes`

Exactement cette chaîne (casse comprise) quand une info **n’est pas encore fournie**. **Ne pas inventer.**

- Distinct de `Non déterminé` / `Inconnue` / `inconnu` : ceux-là sont des réponses **assumées** ; le jeton = case encore vide.
- Un bug peut donc être **complet** ou **incomplet** :
  - **complet** — aucune rubrique / métadonnée ne contient le jeton ;
  - **incomplet** — au moins une occurrence de `Informations manquantes`.
- Titre court (`Bug — …`) : toujours un vrai libellé (pas le jeton).
- `#n` : obligatoire pour tout bug listé (créer l’issue d’abord si besoin).

**Issue GitHub** — titres `##` exacts :

```markdown
## Constat
## Reproductibilité
## Impact
## Cause probable
## À corriger
## Hors périmètre
## Métadonnées
```

**Feuille** — sous le `### Bug — … (#n)`, mêmes rubriques en gras puis **Suivi**.

Exemple feuille (**complet**) :

```markdown
### Bug — données d’un compte visibles par un autre compte (#161)

**Constat :** …

**Reproductibilité :** …

**Impact :** …

**Cause probable :** …

**À corriger :** …

**Hors périmètre :** Aucun.

**Suivi :** [#161](…) (`bug`). Trouvé dans : 1.4.3 · Contexte : test humain · Date : 2026-10-07 · Priorité : non prioritaire.
```

Exemple rubrique manquante :

```markdown
**Cause probable :** Informations manquantes
```

Quand le bug est **pris en charge** (planifié) : via **`/afr`**, **retirer** le bloc `### Bug — … (#n)` de **Plus tard** et en faire (ou l’inclure dans) l’**Objectif** d’une **Prochaine** / **Ensuite**. Ne pas laisser le bug listé en Plus tard une fois numéroté.

Quand le bug est **corrigé** (version livrée) : skill **`finaliser-la-version`** —

1. la PR porte `Fixes #<n>` pour chaque issue `bug` résolue par cette version ;
2. le bloc `### Bug — … (#n)` est absent de **Plus tard** (déjà retiré à la planification, sinon le skill le retire) ;
3. l’issue GitHub `#n` est **Closed** (commentaire de clôture avec `VX.Y.Z` si besoin).

## Recherches

Les notes de recherche amont sont dans [`../recherches/`](../recherches/), pas dans ce fichier.
