/**
 * Déblocages et numéros prévus de la feuille de route de dev.
 *
 * Chaque version à venir (`## Prochaine : <Titre>` / `## Ensuite : <Titre>`)
 * porte un **Nom.** (`kebab-case`, qui l’identifie partout), un **Type.**
 * (majeure, mineure, correctif, ou sans numéro : documentation, analyse,
 * évaluation, process) et une rubrique **Bloquée par.** : `Aucune.`, ou une
 * puce par version qui la bloque (`- **<nom>** — raison`, ou `- **X.Y.Z** —
 * raison` pour une version livrée sous son numéro). Une version bloquante est
 * levée quand elle est dans « Déjà livré », c’est-à-dire fusionnée sur main.
 *
 * L’ancienne forme `## Ensuite : X.Y.Z — Titre`, identifiée par son numéro,
 * sans Nom ni Type, reste lue (règle des versions nommées).
 *
 * De là se calculent, sans jamais se saisir à la main :
 * - la ligne **État.** de chaque version (Ouvrable, ou Bloquée avec ce qui reste) ;
 * - la Prochaine : la première version ouvrable dans l’ordre du fichier ;
 *   les autres sont des Ensuite ;
 * - la ligne **N° prévu.** : à partir de la dernière Release lue dans « Déjà
 *   livré », dans l’ordre du fichier, le prochain numéro de son type. Il
 *   n’identifie jamais une version ; le numéro définitif se fixe à Finalise.
 *
 * Le calcul ne dépend que du fichier : deux branches qui le modifient en
 * parallèle se réconcilient en relançant le script, jamais à la main.
 */

const VERSION = /^## (Prochaine|Ensuite) : (.+)$/;
const ANCIENNE = /^(\d+\.\d+\.\d+) — (.+)$/;
const PUCE_LIVREE = /^- \*\*([^*]+)\*\*/;
// Puce numérotée de la nouvelle forme : `- **X.Y.Z** — Titre (`nom`, [#parent](…), …) : …`.
// Le titre peut contenir des parenthèses : le nom est le premier `(`nom`` suivi
// du lien parent ou d'une parenthèse fermante (pas un `(`code`, …` d'une ancienne puce).
const NOM_DE_PUCE = /^- \*\*[^*]+\*\* — .*?\(`([a-z0-9]+(?:-[a-z0-9]+)*)`(?:,\s*\[|\))/;
const LIVREE_EN = /Livrée en \*\*(\d+\.\d+\.\d+)\*\*/;
const SEMVER = /^\d+\.\d+\.\d+$/;
const BLOQUEUR = /^- \*\*([^*]+)\*\*\s*[—–-]\s*(.+)$/;
const ETAT = /^\*\*État\.\*\*/;
const BLOQUEE_PAR = /^\*\*Bloquée par\.\*\*\s*(.*)$/;
const NOM = /^\*\*Nom\.\*\*\s*(.*)$/;
const NOM_VALIDE = /^`([a-z0-9]+(?:-[a-z0-9]+)*)`$/;
const TYPE = /^\*\*Type\.\*\*\s*(.*?)\.?\s*$/;
const NUMERO_PREVU = /^\*\*N° prévu\.\*\*/;

export const TYPES_NUMEROTES = ['majeure', 'mineure', 'correctif'];
export const TYPES_SANS_NUMERO = ['documentation', 'analyse', 'évaluation', 'process'];

function listeFrancaise(elements) {
  if (elements.length <= 1) return elements.join('');
  return `${elements.slice(0, -1).join(', ')} et ${elements.at(-1)}`;
}

function comparerSemver(a, b) {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i += 1) if (pa[i] !== pb[i]) return pa[i] - pb[i];
  return 0;
}

/** Le prochain numéro de `type` après `numero` (null pour un type sans numéro). */
export function numeroSuivant(numero, type) {
  const [x, y, z] = numero.split('.').map(Number);
  if (type === 'majeure') return `${x + 1}.0.0`;
  if (type === 'mineure') return `${x}.${y + 1}.0`;
  if (type === 'correctif') return `${x}.${y}.${z + 1}`;
  return null;
}

/** Numéro de Release d’une puce de « Déjà livré », ou null (sans Release). */
function releaseDePuce(ligne, id) {
  if (/Sans Release/.test(ligne)) return null;
  const en = ligne.match(LIVREE_EN);
  if (en) return en[1];
  return SEMVER.test(id) ? id : null;
}

/**
 * Lit les versions livrées et à venir : `livrees` (noms et numéros reconnus
 * comme livrés), `puces` (nombre de puces de Déjà livré), `derniereRelease`,
 * et chaque version à venir avec son Nom, son Type et ses bloqueurs.
 */
export function lireFeuille(markdown) {
  const lignes = markdown.split(/\r?\n/);
  const livrees = new Set();
  let puces = 0;
  let derniereRelease = null;
  const versions = [];
  let section = '';
  let courante = null;
  const nomDe = (v) => v.id ?? v.titre;

  for (let i = 0; i < lignes.length; i += 1) {
    const ligne = lignes[i];
    if (ligne.startsWith('## ')) {
      section = ligne.slice(3).trim();
      const v = ligne.match(VERSION);
      courante = null;
      if (v) {
        const ancienne = v[2].trim().match(ANCIENNE);
        courante = {
          id: ancienne ? ancienne[1] : null,
          nom: null,
          numero: ancienne ? ancienne[1] : null,
          titre: (ancienne ? ancienne[2] : v[2]).trim(),
          type: null,
          ligneTitre: i,
          ligneType: null,
          ligneNumero: null,
          bloqueurs: null,
        };
        versions.push(courante);
      }
      continue;
    }
    if (section === 'Déjà livré') {
      const l = ligne.match(PUCE_LIVREE);
      if (!l) continue;
      // Le bandeau compte les puces `**X.Y.Z**` et `**<nom>**` (pas `**1.0.x**`).
      if (SEMVER.test(l[1]) || /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(l[1])) puces += 1;
      livrees.add(l[1]);
      const nom = ligne.match(NOM_DE_PUCE);
      if (nom) livrees.add(nom[1]);
      const release = releaseDePuce(ligne, l[1]);
      if (release && (!derniereRelease || comparerSemver(release, derniereRelease) > 0)) {
        derniereRelease = release;
      }
      continue;
    }
    if (!courante) continue;
    const n = ligne.match(NOM);
    if (n) {
      const valide = n[1].trim().match(NOM_VALIDE);
      if (!valide) {
        throw new Error(`${nomDe(courante)} : « Nom. » attend un nom en kebab-case entre accents graves (\`mon-nom\`).`);
      }
      courante.nom = valide[1];
      courante.id = valide[1];
      continue;
    }
    const t = ligne.match(TYPE);
    if (t) {
      const type = t[1].trim();
      if (![...TYPES_NUMEROTES, ...TYPES_SANS_NUMERO].includes(type)) {
        throw new Error(
          `${nomDe(courante)} : Type inconnu « ${type} » (${[...TYPES_NUMEROTES, ...TYPES_SANS_NUMERO].join(', ')}).`,
        );
      }
      courante.type = type;
      courante.ligneType = i;
      continue;
    }
    if (NUMERO_PREVU.test(ligne)) {
      courante.ligneNumero = i;
      continue;
    }
    const b = ligne.match(BLOQUEE_PAR);
    if (!b) continue;
    if (courante.bloqueurs) {
      throw new Error(`${nomDe(courante)} : rubrique « Bloquée par. » en double.`);
    }
    const reste = b[1].trim();
    if (reste) {
      if (reste !== 'Aucune.') {
        throw new Error(`${nomDe(courante)} : « Bloquée par. » attend « Aucune. » ou une liste de puces.`);
      }
      courante.bloqueurs = [];
      continue;
    }
    courante.bloqueurs = [];
    let j = i + 1;
    while (j < lignes.length && lignes[j].trim() === '') j += 1;
    while (j < lignes.length && lignes[j].startsWith('- ')) {
      const m = lignes[j].match(BLOQUEUR);
      if (!m) throw new Error(`${nomDe(courante)} : puce de « Bloquée par. » illisible : ${lignes[j]}`);
      courante.bloqueurs.push({id: m[1].trim(), raison: m[2].trim()});
      j += 1;
    }
    if (!courante.bloqueurs.length) {
      throw new Error(`${nomDe(courante)} : « Bloquée par. » sans puce (écrire « Aucune. » sinon).`);
    }
  }

  const vus = new Set();
  for (const v of versions) {
    if (!v.id) throw new Error(`« ${v.titre} » : ligne « Nom. » manquante.`);
    if (v.nom && !v.type) throw new Error(`${v.id} : ligne « Type. » manquante.`);
    if (vus.has(v.id)) throw new Error(`${v.id} : version en double dans la feuille de route.`);
    vus.add(v.id);
  }

  return {livrees, puces, derniereRelease, versions};
}

/** Calcule l’état et le N° prévu de chaque version, et vérifie la cohérence des bloqueurs. */
export function calculerDeblocages(markdown) {
  const {livrees, derniereRelease, versions} = lireFeuille(markdown);
  const aVenir = new Map(versions.map((v) => [v.id, v]));

  for (const v of versions) {
    if (!v.bloqueurs) throw new Error(`${v.id} : rubrique « Bloquée par. » manquante.`);
    for (const b of v.bloqueurs) {
      if (b.id === v.id) throw new Error(`${v.id} : se bloque elle-même.`);
      if (!livrees.has(b.id) && !aVenir.has(b.id)) {
        throw new Error(`${v.id} : bloquée par ${b.id}, absente de la feuille de route.`);
      }
    }
  }

  // Un cycle rendrait des versions bloquées pour toujours.
  const visite = new Map();
  const parcourir = (id, chemin) => {
    if (visite.get(id) === 'fini') return;
    if (visite.get(id) === 'en cours') {
      throw new Error(`Bloquages en cycle : ${[...chemin, id].join(' → ')}.`);
    }
    visite.set(id, 'en cours');
    for (const b of aVenir.get(id).bloqueurs) {
      if (aVenir.has(b.id)) parcourir(b.id, [...chemin, id]);
    }
    visite.set(id, 'fini');
  };
  for (const v of versions) parcourir(v.id, []);

  let dernier = derniereRelease ?? '0.0.0';
  const resultat = versions.map((v) => {
    const restants = v.bloqueurs.filter((b) => !livrees.has(b.id)).map((b) => b.id);
    let numeroPrevu = null;
    if (TYPES_NUMEROTES.includes(v.type)) {
      numeroPrevu = numeroSuivant(dernier, v.type);
      dernier = numeroPrevu;
    }
    return {
      id: v.id,
      nom: v.nom,
      numero: v.numero,
      titre: v.titre,
      type: v.type,
      numeroPrevu,
      ligneTitre: v.ligneTitre,
      ligneType: v.ligneType,
      ligneNumero: v.ligneNumero,
      bloqueurs: v.bloqueurs,
      restants,
      ouvrable: restants.length === 0,
      prochaine: false,
    };
  });
  const prochaine = resultat.find((v) => v.ouvrable);
  if (prochaine) prochaine.prochaine = true;
  return resultat;
}

export function ligneEtat(version) {
  if (version.ouvrable) return '**État.** Ouvrable.';
  const reste = listeFrancaise(version.restants.map((n) => `**${n}**`));
  // « n sur m » seulement quand une partie des blocages est déjà levée.
  const leve = version.restants.length < version.bloqueurs.length;
  const part = leve ? ` (${version.restants.length} sur ${version.bloqueurs.length})` : '';
  return `**État.** Bloquée : il reste ${reste}${part}.`;
}

export function ligneNumeroPrevu(version) {
  return version.numeroPrevu ? `**N° prévu.** **${version.numeroPrevu}**` : '**N° prévu.** Aucun (pas de Release).';
}

/**
 * Réécrit la feuille : préfixe Prochaine / Ensuite de chaque titre, ligne
 * **État.** juste sous le titre (ajoutée si absente) et ligne **N° prévu.**
 * d’une version qui a un Type (ajoutée sous **Type.** si absente).
 */
export function reecrireFeuille(markdown) {
  const versions = calculerDeblocages(markdown);
  const fin = markdown.endsWith('\n') ? '\n' : '';
  const lignes = markdown.replace(/\r?\n$/, '').split(/\r?\n/);
  // De la fin vers le début, et dans une version de bas en haut : les
  // insertions ne décalent pas les lignes qui restent à traiter.
  for (const v of [...versions].reverse()) {
    if (v.type) {
      if (v.ligneNumero !== null) lignes[v.ligneNumero] = ligneNumeroPrevu(v);
      else lignes.splice(v.ligneType + 1, 0, '', ligneNumeroPrevu(v));
    }
    const i = v.ligneTitre;
    const titre = v.numero && !v.nom ? `${v.numero} — ${v.titre}` : v.titre;
    lignes[i] = `## ${v.prochaine ? 'Prochaine' : 'Ensuite'} : ${titre}`;
    let j = i + 1;
    while (j < lignes.length && lignes[j].trim() === '') j += 1;
    if (j < lignes.length && ETAT.test(lignes[j])) {
      lignes.splice(i + 1, j - i, '', ligneEtat(v));
    } else {
      lignes.splice(i + 1, 0, '', ligneEtat(v));
    }
  }
  return {markdown: lignes.join('\n') + fin, versions};
}

/**
 * Usage seul (projet sans bandeau d’avancement) :
 *   node scripts/deblocages-feuille-de-route.mjs [--verifier]
 * Réécrit la feuille (État., N° prévu, Prochaine) ; --verifier n’écrit rien
 * et sort en erreur si elle n’est plus à jour.
 */
async function principal() {
  const fs = await import('node:fs');
  const {fileURLToPath} = await import('node:url');
  const path = await import('node:path');
  const racine = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
  const fichier = path.join(racine, 'docs', 'dev', 'feuille-de-route', 'feuille-de-route-dev.md');
  const avant = fs.readFileSync(fichier, 'utf8');
  let resultat;
  try {
    resultat = reecrireFeuille(avant);
  } catch (erreur) {
    console.error(`[deblocages] feuille de route : ${erreur.message}`);
    process.exit(1);
  }
  const ouvrables = resultat.versions.filter((v) => v.ouvrable).map((v) => v.id);
  console.log(`[deblocages] ouvrables : ${ouvrables.join(', ') || 'aucune'}`);
  if (resultat.markdown === avant) return;
  if (process.argv.includes('--verifier')) {
    console.error(
      '[deblocages] feuille périmée (État., N° prévu ou Prochaine) : lance `node scripts/deblocages-feuille-de-route.mjs`.',
    );
    process.exit(1);
  }
  fs.writeFileSync(fichier, resultat.markdown, 'utf8');
  console.log('[deblocages] feuille de route mise à jour.');
}

if (process.argv[1] && import.meta.url === (await import('node:url')).pathToFileURL(process.argv[1]).href) {
  await principal();
}
