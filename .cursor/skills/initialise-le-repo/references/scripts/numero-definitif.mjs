/**
 * Numéro définitif d'une version, à « Finalise la version » (modèle du pack,
 * règle des versions nommées) : le prochain numéro de son **Type.** après la
 * dernière Release finale publiée ; aucun pour un type sans numéro
 * (documentation, analyse, évaluation, process).
 *
 * Pré-releases (essai en staging, `vX.Y.Z-rc.<k>`) : elles ne comptent jamais
 * comme dernière Release. Une pré-release dont la Release finale n'existe
 * pas encore **réserve** son numéro : une autre version prend le suivant de
 * son type. La version qui a déjà une pré-release (notes `Version : <nom>`)
 * garde son numéro.
 *
 * Le diff du rôle optionnel `livrables` (agents/roles.yml, hors `tests/` et
 * `*.md`) ne calcule rien : il repère une incohérence, et Finalise s'arrête
 * pour demander. Rôle absent → pas de contrôle.
 *
 * Usage, depuis la branche de version :
 *   node scripts/numero-definitif.mjs <nom> [--derniere-release vX.Y.Z] [--base origin/main]
 * Affiche une ligne JSON {nom, titre, type, numero, derniereRelease,
 * reserves, preRelease, incoherence}. Sortie 0 ; 1 si incohérence ; 2 si erreur.
 */
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

import {TYPES_NUMEROTES, TYPES_SANS_NUMERO, lireFeuille, numeroSuivant} from './deblocages-feuille-de-route.mjs';

const SEMVER = /^v?(\d+\.\d+\.\d+)$/;

/**
 * { numero, incoherence } pour une version de `type` après `derniereRelease`
 * (null : aucune Release encore). `incoherence` est un message, ou null.
 */
export function numeroDefinitif({type, derniereRelease, toucheLivrables, reserves = [], preRelease = null}) {
  if (TYPES_SANS_NUMERO.includes(type)) {
    return {
      numero: null,
      incoherence: toucheLivrables === true
        ? `version de type ${type} (sans numéro) qui touche des fichiers de livrables : elle arrive chez l’utilisateur, il lui faut un type numéroté, ou ces fichiers n’ont pas leur place dans cette version.`
        : null,
    };
  }
  if (!TYPES_NUMEROTES.includes(type)) {
    throw new Error(`Type inconnu « ${type} » (${[...TYPES_NUMEROTES, ...TYPES_SANS_NUMERO].join(', ')}).`);
  }
  const base = derniereRelease ? String(derniereRelease).match(SEMVER)?.[1] : '0.0.0';
  if (!base) throw new Error(`dernière Release illisible « ${derniereRelease} » (attendu X.Y.Z).`);
  let numero;
  if (preRelease) {
    numero = String(preRelease).match(/(\d+\.\d+\.\d+)/)?.[1];
    if (!numero) throw new Error(`pré-release illisible « ${preRelease} » (attendu vX.Y.Z-rc.<k>).`);
  } else {
    numero = numeroSuivant(base, type);
    while (reserves.includes(numero)) numero = numeroSuivant(numero, type);
  }
  return {
    numero,
    incoherence: toucheLivrables !== false
      ? null
      : `version ${type} qui ne touche aucun fichier de livrables : rien n’arrive chez l’utilisateur, son type devrait être sans numéro.`,
  };
}

/** { nom, titre, type } de la version `nom` en Prochaine / Ensuite de la feuille. */
export function versionDeLaFeuille(markdown, nom) {
  const v = lireFeuille(markdown).versions.find((x) => x.nom === nom);
  if (!v) throw new Error(`${nom} : ni en Prochaine ni en Ensuite de la feuille de route.`);
  return {nom: v.nom, titre: v.titre, type: v.type};
}

// --- Ligne de commande ------------------------------------------------------

const RACINE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function option(nom) {
  const i = process.argv.indexOf(nom);
  return i > 0 ? process.argv[i + 1] : null;
}

/** Chemins du rôle `livrables` de agents/roles.yml ; null quand le rôle est absent. */
function cheminsLivrables() {
  const lignes = fs.readFileSync(path.join(RACINE, 'agents', 'roles.yml'), 'utf8').split(/\r?\n/);
  const debut = lignes.findIndex((l) => /^ {2}livrables:\s*$/.test(l));
  if (debut < 0) return null;
  const chemins = [];
  for (const l of lignes.slice(debut + 1)) {
    if (/^ {2}\S/.test(l)) break;
    const m = l.match(/^\s+-\s+(\S+)/);
    if (m) chemins.push(m[1].replace(/\/$/, ''));
  }
  return chemins;
}

function toucheLivrables(base) {
  const livrables = cheminsLivrables();
  if (!livrables) return null; // rôle optionnel absent : pas de contrôle
  const fichiers = execFileSync('git', ['diff', '--name-only', `${base}...HEAD`], {cwd: RACINE, encoding: 'utf8'})
    .split('\n')
    .filter(Boolean)
    .filter((f) => !f.endsWith('.md') && !f.split('/').includes('tests'));
  return fichiers.some((f) => livrables.some((l) => f === l || f.startsWith(`${l}/`)));
}

const echapper = (texte) => texte.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');

const COMPARER = (a, b) => {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  return pa[0] - pb[0] || pa[1] - pb[1] || pa[2] - pb[2];
};

/**
 * À partir des Releases GitHub ({tag_name, prerelease, draft, body}) :
 * la dernière Release finale, les numéros réservés par des pré-releases
 * d'autres versions sans finale, et la pré-release de la version `nom`.
 */
export function lireReleases(releases, nom) {
  const publiees = releases.filter((r) => !r.draft);
  const finales = publiees
    .filter((r) => !r.prerelease)
    .map((r) => r.tag_name.match(/^v(\d+\.\d+\.\d+)$/)?.[1])
    .filter(Boolean)
    .sort(COMPARER);
  const marque = new RegExp(`^Version : ${echapper(nom)} \\(`, 'm');
  const reserves = [];
  let preRelease = null;
  for (const r of publiees.filter((x) => x.prerelease)) {
    const n = r.tag_name.match(/^v(\d+\.\d+\.\d+)-rc\.\d+$/)?.[1];
    if (!n || finales.includes(n)) continue;
    if (marque.test(r.body ?? '')) preRelease = r.tag_name;
    else if (!reserves.includes(n)) reserves.push(n);
  }
  return {derniereRelease: finales.at(-1) ?? null, reserves: reserves.sort(COMPARER), preRelease};
}

function releasesGithub() {
  return JSON.parse(
    execFileSync('gh', ['api', 'repos/{owner}/{repo}/releases?per_page=100'], {cwd: RACINE, encoding: 'utf8'}),
  );
}

function principal() {
  const nom = process.argv[2];
  if (!nom || nom.startsWith('--')) throw new Error('usage : node scripts/numero-definitif.mjs <nom>');
  const feuille = fs.readFileSync(path.join(RACINE, 'docs', 'dev', 'feuille-de-route', 'feuille-de-route-dev.md'), 'utf8');
  const version = versionDeLaFeuille(feuille, nom);
  const lu = lireReleases(releasesGithub(), nom);
  const derniereRelease = option('--derniere-release') ?? lu.derniereRelease;
  const r = numeroDefinitif({
    type: version.type,
    derniereRelease,
    toucheLivrables: toucheLivrables(option('--base') ?? 'origin/main'),
    reserves: lu.reserves,
    preRelease: lu.preRelease,
  });
  console.log(JSON.stringify({...version, ...r, derniereRelease, reserves: lu.reserves, preRelease: lu.preRelease}));
  if (r.incoherence) {
    console.error(`[numero-definitif] ${nom} : ${r.incoherence}`);
    process.exitCode = 1; // pas process.exit() : sous Windows, stdout/stderr pourraient être coupés
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    principal();
  } catch (e) {
    console.error('[numero-definitif]', e.message);
    process.exitCode = 2;
  }
}
