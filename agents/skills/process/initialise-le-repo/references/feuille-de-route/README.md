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
## Déjà livré          ← puces **X.Y.Z** (Release) ou **<nom>** (sans Release) — titre + résumé court
## Prochaine : <Titre>
## Ensuite : <Titre>     (répétable)
## Plus tard (pas encore planifié)
### … sujets / bugs …
```

| Section | Rôle |
| --- | --- |
| **Déjà livré** | Versions livrées (une puce par version, sous son numéro de Release ou, sans Release, sous son nom). |
| **Prochaine** | Exactement **une** version : la suivante à ouvrir. Avec les blocages : **au plus une**, la **première ouvrable**, calculée. |
| **Ensuite** | Versions planifiées après la Prochaine, dans l’ordre où elles doivent arriver. Avec les blocages : toutes les autres, ouvrables ou bloquées. |
| **Plus tard** | Idées / bugs pas encore planifiés en version (ou reprise plus tard). |

À « Finalise la version » : la version livrée passe en **Déjà livré** ; la première **Ensuite** devient **Prochaine** (avec les blocages : **`/dfr`** recalcule les états, les N° prévus et la Prochaine).

## Conventions d’écriture des versions

### Nom, Type et Numéro prévu

Un seul numéro par version, celui de sa Release, en semver strict ; une version s’identifie par son **Nom**.

- Titre de section : `## Prochaine : <Titre>` ou `## Ensuite : <Titre>`, sans numéro. Le titre peut changer au grilling ; le Nom, jamais.
- Un **seul job** par version (un objectif métier clair).
- Sous le titre : **`Nom.`** `` `<nom>` `` (kebab-case ASCII, unique, jamais changé : branche `version/<nom>`, spec `docs/specs/<nom>.md`, bloqueurs), **`Type.`**, **`N° prévu.`**.

Types :

- **majeure** — tout le monde doit faire un geste (réinstaller, changer d’adresse, migrer des données à la main, mise en production définitive) ; décidé dans ce fichier, jamais calculé ;
- **mineure** — une capacité nouvelle visible par l’utilisateur ;
- **correctif** — une correction ou une amélioration sans capacité nouvelle ;
- **documentation**, **analyse**, **évaluation**, **process** — rien n’arrive chez l’utilisateur : pas de Release, pas de numéro.

**N° prévu.** À partir de la dernière Release lue dans **Déjà livré**, chaque version numérotée prend, dans l’ordre du fichier, le prochain numéro de son type (majeure `X+1.0.0`, mineure `X.Y+1.0`, correctif `X.Y.Z+1`) ; `Aucun (pas de Release).` sinon. Calculé par le script du projet quand il en a un (`scripts/deblocages-feuille-de-route.mjs`, opt-in), sinon tenu par **`/afr`**. Il n’identifie jamais une version.

**Numéro définitif, à « Finalise la version ».** Le prochain numéro libre de son type par rapport à la dernière Release. Avec le rôle optionnel **`livrables`** (`agents/roles.yml` : ce qui entre dans ce que l’utilisateur installe), le diff de la branche repère une incohérence : version sans numéro qui touche `livrables`, ou version numérotée qui n’en touche aucun → Finalise s’arrête et demande.

**Pré-release (rôle optionnel `staging`).** Quand le projet a un environnement staging et que la version a des scénarios Staging, Finalise publie d’abord une pré-release `vX.Y.Z-rc.<k>` (marquée *Pre-release* sur GitHub, notes minimales) pour l’essai en staging, puis la Release finale `vX.Y.Z` sur le même SHA une fois l’essai OK. Une rc **réserve** son numéro : une autre version finalisée entre-temps prend le suivant. Les pré-releases ne comptent jamais comme « dernière Release » pour le **N° prévu**.

Tags `vX.Y.Z`. Parent et PR titrés `<Titre>` ; à Finalise, le commit squash, la Release et le parent prennent `VX.Y.Z — <Titre>`. Notes de Release : `Version : <nom> (#<parent>)`.

Sur le site de doc, une version à venir est présentée par son titre, une version livrée par son numéro de Release, une version sans Release par son titre et « Sans Release ».

### Corps d’une version (Prochaine / Ensuite)

- **`Objectif.`** — ce que l’utilisateur / collaborateur gagne (langage produit).
- **`Hors périmètre`** — ce qui est explicitement reporté (souvent vers une autre version).
- Optionnel : auth / orientation technique / recherche / tests, si utile avant le grilling.
- Pas de détail d’implémentation digne d’une spec ; les décisions figées peuvent pointer vers un ADR ou une issue.

### Blocages (opt-in)

Seulement quand le projet a **`scripts/deblocages-feuille-de-route.mjs`** (script du projet, appelé par son script d’avancement). Sans lui, rien de cette section ne s’applique.

Chaque version (Prochaine / Ensuite) porte alors, dans cet ordre : **`État.`** juste sous le titre (**calculé** par le script, jamais écrit ni fusionné à la main), **`Nom.`**, **`Type.`**, **`N° prévu.`** (calculé), **`Objectif.`**, **`Bloquée par.`** (**toujours présente**), optionnellement **`À trancher au grilling.`**, puis **`Hors périmètre`**.

Une version est **bloquée** par une autre quand une partie de son **Objectif** ne peut pas se faire sans elle. Écrit par **`/afr`** à la création de la version, revu quand un objectif change.

```markdown
**Bloquée par.**

- **credits-initiaux** — les crédits initiaux qu’un participant reçoit à l’inscription n’existent pas encore.
- **1.4.2** — la borne refuse au-delà du débit maximal.
```

- Une puce par version **directement** nécessaire : `- **<nom>** — raison` (ou `- **X.Y.Z** — raison` pour une version déjà livrée sous son numéro), la raison en langage produit (ce qui manque, pas une table ou une route). Les blocages hérités ne se recopient pas.
- Le nom ou le numéro cité est une version de **Déjà livré**, de **Prochaine** ou d’**Ensuite** ; pas de cycle. Le script refuse sinon.
- Une version qui ne dépend de rien : `**Bloquée par.** Aucune.`
- **Levée = fusionnée sur la base.** Un bloqueur est levé quand sa version est dans **Déjà livré**. Une version ouverte, ou dont la PR est prête, ne débloque rien : ne pas ouvrir une version depuis la branche d’une autre (le squash-merge réécrit ses commits).
- **Pas de blocage partiel.** Un bloqueur bloque toute la version. S’il ne touche qu’une partie de l’objectif, on **découpe** avec **`/afr`** : la partie bloquée passe en **Hors périmètre** vers la version qui bloque (si elle y a sa place) ou vers une nouvelle version, et la version perd ce bloqueur. **`/dfr`** signale ces cas, il ne les tranche pas.

**`État.`** se déduit des bloqueurs et de **Déjà livré** :

| État | Quand | Ligne écrite |
| --- | --- | --- |
| Ouvrable | tous ses bloqueurs sont livrés | `**État.** Ouvrable.` |
| Bloquée | il reste au moins un bloqueur | `**État.** Bloquée : il reste **credits-initiaux**.` ; `(n sur m)` quand une partie est déjà levée |

La **Prochaine** est la première version ouvrable dans l’ordre du fichier ; aucune si tout est bloqué. « Ouvre la version » sans nom prend la première ouvrable **pas encore en cours**.

« En cours » (branche `version/<nom>`, ou PR ouverte dont la tête est cette branche) n’est **pas** écrit : une branche non fusionnée est invisible depuis la base. **`/dfr`** et « Ouvre la version » le lisent sur GitHub.

**Versions en parallèle.** Plusieurs versions ouvrables peuvent être ouvertes en même temps. Chacune, fusionnée, débloque ce qui l’attendait, dans l’ordre d’arrivée sur la base. Deux branches qui modifient la feuille se réconcilient en relançant le script après fusion de la base : **État.**, **Prochaine** et le bandeau du README (si le projet en a un) ne se fusionnent jamais à la main. La copie d’une branche peut dater ; celle de la base fait foi.

### Déjà livré

- Avec Release : ``- **X.Y.Z** — <Titre> (`<nom>`, [#parent](…), [spec](…)) : résumé…`` ; le nom en tête des parenthèses lève les bloqueurs qui le citent.
- Sans Release : `- **<nom>** — <Titre> (…) : résumé… Sans Release.`
- Bug connu **livré avec** la version : le mentionner ici **et** le reporter en **Plus tard** / Bug tant qu’il n’est pas corrigé.

## Bugs

Création standardisée : skill **`/cub`** (`creer-un-bug`) — issue GitHub **et** entrée feuille. Ne pas inventer un format parallèle.

Les bugs pas encore planifiés en version vivent sous **`## Plus tard (pas encore planifié)`**.

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
7. **Ce que vous voyez / quoi faire** — pour un collaborateur, en langage simple : ce qu’il voit et quoi faire en attendant ; ou jeton ci-dessous.
8. **Métadonnées** (issue) / **Suivi** (feuille) :
   - Trouvé dans : `X.Y.Z` (Release) \| `<nom>` (version) \| `inconnu` \| jeton
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
## Ce que vous voyez / quoi faire
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

**Ce que vous voyez / quoi faire :** la liste affiche les dossiers d’un autre compte. En attendant, déconnectez-vous puis reconnectez-vous avant d’ouvrir la liste.

**Suivi :** [#161](…) (`bug`). Trouvé dans : 1.4.3 · Contexte : test humain · Date : 2026-10-07 · Priorité : non prioritaire.
```

Exemple rubrique manquante :

```markdown
**Cause probable :** Informations manquantes
```

Quand le bug est **pris en charge** (planifié) : via **`/afr`**, **retirer** le bloc `### Bug — … (#n)` de **Plus tard** et en faire (ou l’inclure dans) l’**Objectif** d’une **Prochaine** / **Ensuite**. Ne pas laisser le bug listé en Plus tard une fois planifié.

Quand le bug est **corrigé** (version livrée) : skill **`finaliser-la-version`** —

1. la PR porte `Fixes #<n>` pour chaque issue `bug` résolue par cette version ;
2. le bloc `### Bug — … (#n)` est absent de **Plus tard** (déjà retiré à la planification, sinon le skill le retire) ;
3. l’issue GitHub `#n` est **Closed** (commentaire de clôture avec `VX.Y.Z` si besoin).

## Recherches

Les notes de recherche amont sont dans [`../recherches/`](../recherches/), pas dans ce fichier.
