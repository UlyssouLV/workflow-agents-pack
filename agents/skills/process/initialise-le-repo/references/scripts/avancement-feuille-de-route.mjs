/**
 * Avancement de la feuille de route de dev, affiché dans le README.
 *
 * Compte les versions de « Déjà livré » (puces `- **X.Y.Z** — …` ou
 * `- **<nom>** — …`) et celles qui restent (titres `## Prochaine : <Titre>`
 * et `## Ensuite : <Titre>`, ou l’ancienne forme `X.Y.Z — <Titre>`).
 * « Plus tard » n’est pas planifié : il n’entre pas dans le total.
 * Avancement = livrées / (livrées + restantes), arrondi à l’entier.
 *
 * Recalcule d’abord les déblocages (scripts/deblocages-feuille-de-route.mjs) :
 * ligne **État.** de chaque version, ligne **N° prévu.** (dernière Release,
 * ordre, Type) et Prochaine = première version ouvrable.
 *
 * Écrit la feuille de route ainsi recalculée, l’image
 * docs/img/avancement-feuille-de-route.svg et le bloc du README entre
 * <!-- sync:avancement-feuille-de-route --> … <!-- /sync:… -->, qui liste
 * sous le bandeau les versions ouvrables.
 * Lit seulement le dépôt : ni réseau, ni jeton.
 *
 * --verifier : n’écrit rien ; sort en erreur si la feuille (État., N° prévu,
 * Prochaine), le README ou l’image ne correspondent plus (check de PR).
 *
 * Usage : node scripts/avancement-feuille-de-route.mjs [--verifier]
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

import {calculerDeblocages, lireFeuille, reecrireFeuille} from './deblocages-feuille-de-route.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..');
const FEUILLE = path.join(REPO_ROOT, 'docs', 'dev', 'feuille-de-route', 'feuille-de-route-dev.md');
const README = path.join(REPO_ROOT, 'README.md');
const IMAGE_RELATIVE = 'docs/img/avancement-feuille-de-route.svg';
const FEUILLE_RELATIVE = 'docs/dev/feuille-de-route/feuille-de-route-dev.md';
const IMAGE = path.join(REPO_ROOT, IMAGE_RELATIVE);
const START = '<!-- sync:avancement-feuille-de-route -->';
const END = '<!-- /sync:avancement-feuille-de-route -->';

const ROUGE = '#c8102e';
const ROUGE_CLAIR = '#ff4d5e';
const BLEU_NUIT = '#0f2338';
const BLEU = '#1e3a5f';
const BLEU_PISTE = '#2a4a73';

export function lireAvancement(markdown) {
  const {puces} = lireFeuille(markdown);
  const versions = calculerDeblocages(markdown);
  const total = puces + versions.length;
  if (!total) throw new Error('Aucune version trouvée dans la feuille de route.');
  return {
    livrees: puces,
    restantes: versions.length,
    total,
    pourcentage: Math.round((puces * 100) / total),
    prochaine: versions.find((v) => v.prochaine) ?? null,
  };
}

/** Une version à venir telle qu’affichée : son titre (`X.Y.Z — titre` dans l’ancienne forme). */
export function libelleVersion(version) {
  return version.numero && !version.nom ? `${version.numero} — ${version.titre}` : version.titre;
}

function echapper(texte) {
  return texte
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function pluriel(n, mot) {
  return `${n} ${mot}${n > 1 ? 's' : ''}`;
}

export function genererSvg({livrees, restantes, total, pourcentage, prochaine}) {
  const largeur = 760;
  const hauteur = 168;
  const marge = 32;
  const barreY = 92;
  const barreH = 18;
  const ecart = 4;
  const largeurBarre = largeur - 2 * marge;
  const segment = (largeurBarre - ecart * (total - 1)) / total;

  const segments = [];
  for (let i = 0; i < total; i += 1) {
    const x = (marge + i * (segment + ecart)).toFixed(2);
    const livre = i < livrees;
    segments.push(
      `<rect x="${x}" y="${barreY}" width="${segment.toFixed(2)}" height="${barreH}" rx="3" fill="${livre ? 'url(#rempli)' : BLEU_PISTE}"${livre ? '' : ' fill-opacity="0.55"'}/>`,
    );
  }

  const suite = prochaine
    ? `Prochaine : ${libelleVersion(prochaine)}`
    : 'Toutes les versions prévues sont livrées';

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${largeur}" height="${hauteur}" viewBox="0 0 ${largeur} ${hauteur}" role="img" aria-label="Feuille de route : ${pourcentage} %">
  <title>Feuille de route : ${pourcentage} % (${livrees} versions livrées sur ${total})</title>
  <defs>
    <linearGradient id="fond" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="${BLEU_NUIT}"/>
      <stop offset="1" stop-color="${BLEU}"/>
    </linearGradient>
    <linearGradient id="rempli" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="${ROUGE}"/>
      <stop offset="1" stop-color="${ROUGE_CLAIR}"/>
    </linearGradient>
  </defs>
  <rect width="${largeur}" height="${hauteur}" rx="16" fill="url(#fond)"/>
  <g font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif">
    <text x="${marge}" y="44" fill="#ffffff" fill-opacity="0.65" font-size="13" font-weight="600" letter-spacing="2">FEUILLE DE ROUTE · BBASS AGENTS IA</text>
    <text x="${marge}" y="74" fill="#ffffff" font-size="22" font-weight="700">${pluriel(livrees, 'version')} ${livrees > 1 ? 'livrées' : 'livrée'} sur ${total}</text>
    <text x="${largeur - marge}" y="74" text-anchor="end" fill="url(#rempli)" font-size="48" font-weight="800">${pourcentage} %</text>
    ${segments.join('\n    ')}
    <text x="${marge}" y="140" fill="#ffffff" fill-opacity="0.8" font-size="14">${echapper(suite)}</text>
    <text x="${largeur - marge}" y="140" text-anchor="end" fill="#ffffff" fill-opacity="0.8" font-size="14">${pluriel(restantes, 'version')} ${restantes > 1 ? 'restantes' : 'restante'}</text>
  </g>
</svg>
`;
}

function badge(libelle, valeur, couleur, alt) {
  const enc = (t) => encodeURIComponent(t.replaceAll('-', '--').replaceAll('_', '__').replaceAll(' ', '_'));
  const url = `https://img.shields.io/badge/${enc(libelle)}-${enc(valeur)}-${couleur}?style=for-the-badge`;
  return `<a href="${FEUILLE_RELATIVE}"><img src="${url}" alt="${echapper(alt)}" /></a>`;
}

function blocOuvrables(versions) {
  if (!versions.length) return '';
  const ouvrables = versions.filter((v) => v.ouvrable);
  const bloquees = versions.length - ouvrables.length;
  const titre = ouvrables.length
    ? `<b>${ouvrables.length > 1 ? 'Ouvrables maintenant' : 'Ouvrable maintenant'}</b>`
    : '<b>Aucune version ouvrable</b>';
  const lignes = ouvrables.map(
    (v) => `  ${echapper(libelleVersion(v))}${v.prochaine ? ' <i>(Prochaine)</i>' : ''}`,
  );
  const badges = [
    badge('ouvrables', String(ouvrables.length), '1b6b3a', `${ouvrables.length} versions ouvrables`),
    badge('bloquées', String(bloquees), BLEU.slice(1), `${bloquees} versions bloquées`),
    badge('feuille de route', '→', BLEU_NUIT.slice(1), 'Toute la feuille de route'),
  ];
  return `
<p align="center">
  ${titre}${lignes.length ? '<br />' : ''}
${lignes.join('<br />\n')}
</p>
<p align="center">
  ${badges.join('\n  ')}
</p>`;
}

export function blocReadme({livrees, restantes, total, pourcentage}, versions = []) {
  const alt = `Feuille de route : ${pourcentage} % (${livrees} versions livrées sur ${total}, ${restantes} restantes)`;
  return `${START}
<p align="center">
  <a href="${FEUILLE_RELATIVE}"><img src="${IMAGE_RELATIVE}" alt="${alt}" width="760" /></a>
</p>${blocOuvrables(versions)}
${END}`;
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function readmeAttendu(readme, bloc) {
  if (!readme.includes(START) || !readme.includes(END)) {
    throw new Error(`Marqueurs manquants dans README.md (${START} … ${END}).`);
  }
  return readme.replace(new RegExp(`${escapeRegExp(START)}[\\s\\S]*?${escapeRegExp(END)}`), bloc);
}

function lireSiPresent(fichier) {
  return fs.existsSync(fichier) ? fs.readFileSync(fichier, 'utf8') : null;
}

function main() {
  const feuille = fs.readFileSync(FEUILLE, 'utf8');
  let recalcul;
  try {
    recalcul = reecrireFeuille(feuille);
  } catch (erreur) {
    console.error(`[avancement] feuille de route : ${erreur.message}`);
    process.exit(1);
  }
  const avancement = lireAvancement(recalcul.markdown);
  const ouvrables = recalcul.versions.filter((v) => v.ouvrable).map((v) => v.id);
  console.log(
    `[avancement] ${avancement.livrees} livrées · ${avancement.restantes} restantes · ${avancement.pourcentage} % · ouvrables : ${ouvrables.join(', ') || 'aucune'}`,
  );

  const readme = fs.readFileSync(README, 'utf8');
  const attendus = [
    [FEUILLE, feuille, recalcul.markdown],
    [README, readme, readmeAttendu(readme, blocReadme(avancement, recalcul.versions))],
    [IMAGE, lireSiPresent(IMAGE), genererSvg(avancement)],
  ];
  const perimes = attendus.filter(([, actuel, attendu]) => actuel !== attendu);

  if (process.argv.includes('--verifier')) {
    if (!perimes.length) {
      console.log('[avancement] README à jour.');
      return;
    }
    const fichiers = perimes.map(([f]) => path.relative(REPO_ROOT, f)).join(', ');
    console.error(
      `[avancement] ${fichiers} ne suit plus les bloqueurs de la feuille de route. ` +
        'Lance `node scripts/avancement-feuille-de-route.mjs` puis commite le résultat.',
    );
    process.exit(1);
  }

  if (!perimes.length) {
    console.log('[avancement] README déjà à jour.');
    return;
  }
  fs.mkdirSync(path.dirname(IMAGE), {recursive: true});
  for (const [fichier, , attendu] of perimes) fs.writeFileSync(fichier, attendu, 'utf8');
  console.log(`[avancement] mis à jour : ${perimes.map(([f]) => path.relative(REPO_ROOT, f)).join(', ')}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
