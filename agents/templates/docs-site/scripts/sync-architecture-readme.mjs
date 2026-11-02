/**
 * Copie le bloc Mermaid de docs/architecture/vue-systeme.md dans le README
 * (entre les marqueurs sync:vue-systeme-mermaid). Sans ce fichier ou sans les
 * marqueurs dans le README : rien à faire (opt-in).
 *
 * Usage : node scripts/sync-architecture-readme.mjs
 */
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../..');
const SOURCE = path.join(REPO_ROOT, 'docs/architecture/vue-systeme.md');
const README = path.join(REPO_ROOT, 'README.md');

const START = '<!-- sync:vue-systeme-mermaid -->';
const END = '<!-- /sync:vue-systeme-mermaid -->';

function extraireMermaid(markdown) {
  const match = markdown.match(/```mermaid\r?\n([\s\S]*?)```/);
  if (!match) {
    throw new Error(`Aucun bloc \`\`\`mermaid dans ${SOURCE}`);
  }
  return match[1].replace(/\s+$/, '') + '\n';
}

function main() {
  if (!fs.existsSync(SOURCE)) {
    console.log('[sync-arch] pas de docs/architecture/vue-systeme.md : rien à faire.');
    return;
  }
  const source = fs.readFileSync(SOURCE, 'utf8');
  const mermaid = extraireMermaid(source);
  const bloc = `${START}\n\`\`\`mermaid\n${mermaid}\`\`\`\n${END}`;

  let readme = fs.readFileSync(README, 'utf8');
  if (!readme.includes(START) || !readme.includes(END)) {
    console.log(`[sync-arch] pas de marqueurs ${START} dans README.md : rien à faire.`);
    return;
  }
  const pattern = new RegExp(
    `${escapeRegExp(START)}[\\s\\S]*?${escapeRegExp(END)}`,
  );
  const apres = readme.replace(pattern, bloc);
  if (apres === readme) {
    console.log('[sync-arch] README déjà à jour.');
    return;
  }
  fs.writeFileSync(README, apres, 'utf8');
  console.log('[sync-arch] README ← docs/architecture/vue-systeme.md');
}

function escapeRegExp(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

main();
