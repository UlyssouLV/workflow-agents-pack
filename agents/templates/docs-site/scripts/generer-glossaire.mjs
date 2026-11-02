/**
 * docs/glossaire.md → src/data/glossaire.cjs, lu par le plugin remark
 * src/remark/glossaire.cjs qui relie les termes dans toute la doc.
 *
 * Un terme = un titre `## Terme {#slug}` (sans `{#slug}`, slug tiré du titre).
 * Formes reconnues : le terme, son pluriel simple (+ s, terme d'un mot), et les formes de la
 * ligne optionnelle `Formes : Caméras, caméra simulée` sous le titre (à
 * utiliser pour un pluriel irrégulier ou composé). La casse est ignorée.
 * `Formes : aucune` : terme jamais lié (mot trop courant dans la doc).
 * Résumé (infobulle) : première phrase du premier paragraphe.
 *
 * Usage : node scripts/generer-glossaire.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const SOURCE = path.join(REPO_ROOT, 'docs/glossaire.md');
const OUT = path.join(__dirname, '../src/data/glossaire.cjs');

function slugDe(titre) {
  return titre
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function texteBrut(markdown) {
  return markdown
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/[*_`]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function premierePhrase(texte) {
  const m = texte.match(/^.+?[.!?](?=\s|$)/);
  return m ? m[0] : texte;
}

/** Pluriel des termes d'un mot seulement ; un composé passe par `Formes :`. */
function pluriel(terme) {
  return /\s/.test(terme) || /[sxz]$/i.test(terme) ? null : `${terme}s`;
}

export function parserGlossaire(markdown) {
  const termes = [];
  const sections = markdown.split(/^## /m).slice(1);
  for (const section of sections) {
    const [entete, ...lignes] = section.split('\n');
    const m = entete.match(/^(.+?)\s*(?:\{#([\w-]+)\})?\s*$/);
    if (!m) continue;
    const terme = m[1].trim();
    const corps = lignes.join('\n');
    const formesLigne = corps.match(/^Formes\s*:\s*(.+)$/m);
    if (formesLigne && formesLigne[1].trim().toLowerCase() === 'aucune') continue;
    const formes = new Set([terme, pluriel(terme)].filter(Boolean));
    if (formesLigne) {
      for (const forme of formesLigne[1].split(',')) {
        if (forme.trim()) formes.add(forme.trim());
      }
    }
    const paragraphe = corps
      .split(/\n\s*\n/)
      .map((bloc) => bloc.trim())
      .find((bloc) => bloc && !/^(Formes|À éviter)\s*:/.test(bloc));
    termes.push({
      formes: [...formes],
      slug: m[2] || slugDe(terme),
      resume: paragraphe ? premierePhrase(texteBrut(paragraphe)) : '',
    });
  }
  // Du plus long au plus court : « Caméra simulée » avant « Caméra ».
  return termes.sort(
    (a, b) =>
      Math.max(...b.formes.map((f) => f.length)) -
      Math.max(...a.formes.map((f) => f.length)),
  );
}

function main() {
  const markdown = fs.existsSync(SOURCE) ? fs.readFileSync(SOURCE, 'utf8') : '';
  const termes = parserGlossaire(markdown);
  const contenu = `/** Généré par scripts/generer-glossaire.mjs depuis docs/glossaire.md — ne pas éditer. */
const TERMES_GLOSSAIRE = ${JSON.stringify(termes, null, 2)};

module.exports = {TERMES_GLOSSAIRE};
`;
  fs.mkdirSync(path.dirname(OUT), {recursive: true});
  fs.writeFileSync(OUT, contenu, 'utf8');
  console.log(`[glossaire] ${termes.length} terme(s) → src/data/glossaire.cjs`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}
