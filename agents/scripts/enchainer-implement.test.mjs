// node --test agents/scripts/enchainer-implement.test.mjs
// Branche Windows d'enchainer-implement.sh, jouée sur n'importe quel OS : uname,
// cygpath, wt.exe, cmd.exe, pwsh et claude sont de faux exécutables qui notent
// leurs arguments. Le PATH ne contient qu'eux : aucun vrai terminal ne s'ouvre.
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {dirname, join} from 'node:path';
import {afterEach, beforeEach, test} from 'node:test';
import {fileURLToPath} from 'node:url';

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), 'enchainer-implement.sh');

// Le bash qui lance ce test (Git Bash sous Windows, jamais celui de WSL).
const BASH = process.platform === 'win32'
  ? spawnSync('cygpath', ['-w', '/usr/bin/bash'], {encoding: 'utf8'}).stdout.trim() || 'bash'
  : '/bin/bash';

// Faux cygpath : /un/chemin <-> W:\un\chemin. FAUX_CYGPATH_ABSENT simule un
// clone que Windows ne retrouve pas.
const CYGPATH = `#!/bin/bash
if [ "$1" = "-w" ]; then
  if [ -n "\${FAUX_CYGPATH_ABSENT:-}" ]; then printf '%s\\n' 'W:\\introuvable\\clone'; exit 0; fi
  p="$2"; printf 'W:%s\\n' "\${p//\\//\\\\}"
elif [ "$1" = "-u" ]; then
  p="\${2#W:}"; printf '%s\\n' "\${p//\\\\//}"
fi
`;

// Faux exécutable : une ligne par argument dans <journal>/<nom>.args.
const faux = (nom) => `#!/bin/bash
for a in "$@"; do printf '%s\\n' "$a"; done > "$JOURNAL/${nom}.args"
`;

let racine;
let bin;
let journal;
let clone;

beforeEach(() => {
  racine = mkdtempSync(join(tmpdir(), 'enchainer-'));
  bin = join(racine, 'bin');
  journal = join(racine, 'journal');
  clone = join(racine, 'Dossiers individuels par Collaborateur', 'Ulysse LONG', 'BBASS-Agents-IA');
  for (const d of [bin, journal, join(clone, 'agents', 'skills')]) mkdirSync(d, {recursive: true});
  ecrire('uname', '#!/bin/bash\necho MINGW64_NT-10.0-26300\n');
  ecrire('cygpath', CYGPATH);
  for (const nom of ['wt.exe', 'cmd.exe', 'pwsh', 'claude']) ecrire(nom, faux(nom));
});

afterEach(() => rmSync(racine, {recursive: true, force: true}));

function ecrire(nom, contenu) {
  writeFileSync(join(bin, nom), contenu);
  chmodSync(join(bin, nom), 0o755);
}

function lancer(env = {}) {
  return spawnSync(BASH, [SCRIPT, '42'], {
    cwd: clone,
    encoding: 'utf8',
    env: {PATH: posix(bin), JOURNAL: journal, ...env},
  });
}

const args = (nom) => readFileSync(join(journal, `${nom}.args`), 'utf8').split('\n').slice(0, -1);
// Chemin tel que bash le voit (/c/Users/… sous Git Bash), puis tel que le faux
// cygpath -w le traduit.
const posix = (p) => spawnSync(BASH, ['-c', 'pwd'], {cwd: p, encoding: 'utf8'}).stdout.trim();
const cheminWindows = (dossier, fichier) =>
  'W:' + (posix(dossier) + (fichier ? `/${fichier}` : '')).replaceAll('/', '\\');

test('wt.exe ouvre la fenêtre dans le clone (chemin Windows à espaces) et lance claude dans PowerShell', () => {
  const r = lancer();
  assert.equal(r.status, 0, r.stderr);
  const a = args('wt.exe');
  assert.deepEqual(a.slice(0, 3), ['new-tab', '-d', cheminWindows(clone)]);
  assert.equal(a[3], cheminWindows(bin, 'pwsh'));
  assert.ok(!a.some((x) => /(^|[\\/])bash(\.exe)?$/.test(x)), `bash dans la commande : ${a}`);
  const commande = a[a.indexOf('-Command') + 1];
  assert.match(commande, /claude '\/implement #42'/);
});

test('sans pwsh, PowerShell Windows (powershell.exe) prend le relais', () => {
  rmSync(join(bin, 'pwsh'));
  ecrire('powershell.exe', faux('powershell.exe'));
  const r = lancer();
  assert.equal(r.status, 0, r.stderr);
  assert.equal(args('wt.exe')[3], cheminWindows(bin, 'powershell.exe'));
});

test('sans wt.exe, cmd start /D ouvre la fenêtre dans le clone', () => {
  rmSync(join(bin, 'wt.exe'));
  const r = lancer();
  assert.equal(r.status, 0, r.stderr);
  const a = args('cmd.exe');
  assert.deepEqual(a.slice(0, 5), ['/c', 'start', '', '/D', cheminWindows(clone)]);
  assert.equal(a[5], cheminWindows(bin, 'pwsh'));
  assert.match(a[a.indexOf('-Command') + 1], /claude '\/implement #42'/);
});

test('un clone que Windows ne retrouve pas fait échouer le script sans ouvrir de fenêtre', () => {
  const r = lancer({FAUX_CYGPATH_ABSENT: '1'});
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /introuvable/);
  assert.ok(!existsSync(join(journal, 'wt.exe.args')));
});

test('ni wt.exe ni cmd.exe : le script échoue avec un message clair', () => {
  rmSync(join(bin, 'wt.exe'));
  rmSync(join(bin, 'cmd.exe'));
  const r = lancer();
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /ni wt\.exe ni cmd\.exe/);
});

test('ni pwsh ni powershell : le script échoue avec un message clair', () => {
  rmSync(join(bin, 'pwsh'));
  const r = lancer();
  assert.notEqual(r.status, 0);
  assert.match(r.stderr, /PowerShell/);
  assert.ok(!existsSync(join(journal, 'wt.exe.args')));
});
