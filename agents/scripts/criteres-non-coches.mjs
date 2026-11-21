/**
 * Garde de fermer-ticket-enfant (`/cci`, spec 1.6.6) : un enfant ne se ferme
 * pas tant qu'une case `- [ ]` reste dans sa partie `## Acceptance criteria`,
 * sauf un critère marqué « vérifié par un humain : … » (repris par le plan de
 * tests humains). Les cases des autres parties ne comptent pas.
 *
 * Usage : node agents/scripts/criteres-non-coches.mjs <n>
 * (lit le corps par `gh issue view <n> --json body`).
 * Sortie 0 : rien de vide ; 1 : cases vides, citées sur stderr ; 2 : erreur.
 */
import {execFileSync} from 'node:child_process';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const HUMAIN = /vérifié par un humain\s*:/i;

/** Texte des cases vides de `## Acceptance criteria`, hors critères vérifiés par un humain. */
export function criteresNonCoches(body) {
  const lignes = String(body || '').split(/\r?\n/);
  const debut = lignes.findIndex((l) => /^##\s+Acceptance criteria\s*$/i.test(l.trim()));
  if (debut < 0) return [];
  const vides = [];
  for (const ligne of lignes.slice(debut + 1)) {
    if (/^#{1,2}\s/.test(ligne)) break;
    const m = ligne.match(/^\s*[-*]\s+\[ \]\s+(.+?)\s*$/);
    if (m && !HUMAIN.test(m[1])) vides.push(m[1]);
  }
  return vides;
}

function principal() {
  const numero = String(process.argv[2] || '').replace(/^#/, '');
  if (!/^\d+$/.test(numero)) throw new Error('usage : node agents/scripts/criteres-non-coches.mjs <n>');
  const {body} = JSON.parse(execFileSync('gh', ['issue', 'view', numero, '--json', 'body'], {encoding: 'utf8'}));
  const vides = criteresNonCoches(body);
  if (!vides.length) {
    console.log(`[criteres] #${numero} : toutes les cases des Acceptance criteria sont cochées.`);
    return;
  }
  console.error(`[criteres] #${numero} : ${vides.length} case(s) vide(s) dans Acceptance criteria :`);
  for (const v of vides) console.error(`- [ ] ${v}`);
  process.exitCode = 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    principal();
  } catch (e) {
    console.error('[criteres]', e.message);
    process.exitCode = 2;
  }
}
