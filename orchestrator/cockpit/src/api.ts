// Contrat de l’API du runtime (`wap_runtime.cockpit`), lu sans transformation.

export type EtatAuth = "connecte" | "sans_token" | "token_refuse" | "injoignable";

export interface Auth {
  etat: EtatAuth;
  compte: string | null;
}

/** Un agent de l’encart Agents : `connecte` = token présent dans `secrets.env`. */
export interface Agent {
  id: "claude" | "cursor";
  nom: string;
  connecte: boolean;
  /** À lancer sur l’hôte pour le connecter. */
  commande: string;
}

export interface Etape {
  numero: number | null;
  libelle: string;
  humain: boolean;
}

export type EtatCi = "echec" | "en_cours" | "ok" | "aucune";

export interface Progression {
  completed: number;
  total: number;
}

export interface PrResume {
  numero: number;
  url: string;
  brouillon: boolean;
  ci: EtatCi;
}

export interface VersionResume {
  numero: number;
  titre: string;
  url: string;
  progression: Progression;
  etape: Etape;
  pr: PrResume | null;
}

/** Activité d’une session ouverte, remontée par les hooks (`inconnue` au départ). */
export type ActiviteSession = "travaille" | "attend" | "inconnue";

/** Lien vers une session ouverte (au plus une par repo, ADR 0007). */
export interface LienSession {
  id: string;
  url: string;
  repo: string;
  activite?: ActiviteSession | null;
}

/** `interrompue` : le runner a redémarré pendant la session. `enchaînée` : close par l’ouverture
 * de sa `suivante`, à la demande de son agent (ADR 0006). */
export type EtatSession = "ouverte" | "terminée" | "échouée" | "interrompue" | "enchaînée";

/** `GET /api/sessions/{id}` : `jobs/<id>/session.json`, écrit par le runner. */
export interface Session {
  id: string;
  url: string;
  repo: string;
  /** `null` : session libre ; un numéro : session `/implement #n` (enchaînée). */
  ticket: number | null;
  /** Branche du clone au lancement ; `null` sur une session d’avant 0.4.2. */
  branche: string | null;
  agent: Agent["id"];
  commande: string;
  debut: string;
  fin: string | null;
  etat: EtatSession;
  code_sortie: number | null;
  /** Identifiants des sessions voisines dans la chaîne ; `null` hors chaîne. */
  precedente: string | null;
  suivante: string | null;
  activite: ActiviteSession;
  skill: string | null;
  /** Premier message soumis, sinon le nom de l’agent. */
  titre: string;
  /** ID Cursor effectif ; `null` = Auto, Claude, ou session d’avant 0.5.1. */
  modele: string | null;
}

/** Une ligne de `GET /api/repos` : `erreur` non nulle → ni étape ni versions. */
export interface Repo<V = VersionResume> {
  slug: string;
  nom: string | null;
  url: string;
  lu_a: string;
  erreur: string | null;
  etape: Etape | null;
  humain_requis: boolean;
  versions: V[];
  /** Session ouverte sur ce repo (badge « Session en cours »). */
  session: LienSession | null;
  /** Toggle Pilote persisté dans `repos.toml`. */
  pilote: boolean;
  /** Agent préféré du pilote (`claude` | `cursor`). */
  agent: Agent["id"];
  /** Préférence modèle Cursor (`null` = Auto). */
  modele: string | null;
  /** Pause/stop du pilote (`null` si OFF, en surveillance, ou prêt à lancer). */
  pilote_stop:
    | "attend"
    | "humain_requis"
    | "echouee"
    | "interrompue"
    | "aucun_eligible"
    | "echec_lancement"
    | null;
}

export interface Liste {
  auth: Auth;
  agents: Agent[];
  /** Registry illisible. */
  erreur: string | null;
  repos: Repo[];
}

export interface Enfant {
  numero: number;
  titre: string;
  url: string;
  ouvert: boolean;
  labels: string[];
  bloque: boolean;
  /** Par agent : pourquoi `/implement #n` est grisé, `null` s’il est possible. */
  lancement: Record<Agent["id"], string | null>;
}

export interface Check {
  nom: string;
  etat: EtatCi;
  url: string | null;
}

export interface Version extends Omit<VersionResume, "pr"> {
  enfants: Enfant[];
  pr: (PrResume & { titre: string; branche: string; checks: Check[] }) | null;
  signaux: Etape[];
}

export interface Bug {
  numero: number;
  titre: string;
  url: string;
  labels: string[];
}

export interface BranchesSession {
  proposees: string[];
  defaut: string;
}

/** `GET /api/repos/{owner}/{name}`. */
export interface Detail extends Omit<Repo<Version>, "session"> {
  bugs: Bug[];
  agents: Agent[];
  /** Session ouverte de ce repo, s’il y en a une (ADR 0007). */
  session: LienSession | null;
  branches: BranchesSession;
}

/** Changement non commité du clone géré (`git status --porcelain` : `M`, `??`…). */
export interface FichierModifie {
  statut: string;
  chemin: string;
}

/** `409` au lancement : le clone géré a des changements non commités, rien n’est lancé. */
export interface CloneSale {
  fichiers: FichierModifie[];
  /** `git diff HEAD` et les fichiers non suivis. */
  diff: string;
  /** Branche actuelle du clone (celle de **Reprendre**). */
  branche: string;
}

/** Réponse au clone sale : **Reprendre** sur l’arbre tel quel, ou **Jeter** (patch gardé). */
export type ChoixClone = "reprendre" | "jeter";

/** Identifiant de session du runtime (`wap_runtime.sessions`) : seul ce motif sert à bâtir une URL. */
export const ID_SESSION = /^\d{8}-\d{6}-[0-9a-f]{6}$/;

export class ErreurApi extends Error {
  /** `409` : la session déjà ouverte. */
  session: LienSession | null = null;
  /** `409` : le clone sale, à reprendre ou jeter. */
  clone: CloneSale | null = null;
}

/** Session serveur expirée / absente : vers la surface de login. */
async function fetchAuthentifie(chemin: string, init?: RequestInit): Promise<Response> {
  const reponse = await fetch(chemin, init);
  if (reponse.status === 401) {
    window.location.assign("/login");
  }
  return reponse;
}

export async function lire<T>(chemin: string): Promise<T> {
  const reponse = await fetchAuthentifie(chemin, { headers: { Accept: "application/json" } });
  if (!reponse.ok) {
    // FastAPI rend `{"detail": "<message>"}` (404 : repo absent du registry).
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `${chemin} : HTTP ${reponse.status}`);
  }
  return (await reponse.json()) as T;
}

/** `POST /api/cockpit/login` : pose le cookie de session serveur (httpOnly). */
export async function connecterCockpit(login: string, password: string): Promise<void> {
  const reponse = await fetch("/api/cockpit/login", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ login, password }),
  });
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `login : HTTP ${reponse.status}`);
  }
}

/** `POST /api/cockpit/logout` puis retour à `/login`. */
export async function deconnecterCockpit(): Promise<void> {
  await fetchAuthentifie("/api/cockpit/logout", {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  window.location.assign("/login");
}

/** `GET /api/sessions` et `GET /api/repos/{owner}/{name}/sessions` : plus récentes d’abord. */
export interface SessionsDuRepo {
  sessions: Session[];
}

/** `GET /api/sessions/{id}/terminal.cast` : le terminal enregistré (asciinema v2), en texte. */
export async function lireEnregistrement(id: string): Promise<string> {
  if (!ID_SESSION.test(id)) throw new ErreurApi(`session invalide : ${id}`);
  const chemin = `/api/sessions/${encodeURIComponent(id)}/terminal.cast`;
  const reponse = await fetchAuthentifie(chemin);
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `${chemin} : HTTP ${reponse.status}`);
  }
  return reponse.text();
}

/** Une entrée de `GET /api/modeles` (`id` nul = Auto). */
export interface ModeleCursor {
  id: string | null;
  libelle: string;
}

/** `PATCH /api/repos/{owner}/{name}` : toggle Pilote, agent et modèle préféré. */
export async function enregistrerPilote(
  repo: string,
  pilote: boolean,
  agent: Agent["id"],
  modele?: string | null,
): Promise<{ pilote: boolean; agent: Agent["id"]; modele: string | null }> {
  const reponse = await fetchAuthentifie(`/api/repos/${repo}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(modele === undefined ? { pilote, agent } : { pilote, agent, modele }),
  });
  const corps = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    throw new ErreurApi(corps?.detail ?? `pilote : HTTP ${reponse.status}`);
  }
  return corps as { pilote: boolean; agent: Agent["id"]; modele: string | null };
}

/** `POST /api/sessions` ; le navigateur y joint l’en-tête `Origin` que le runtime vérifie. */
export async function lancerSession(
  repo: string,
  agent: Agent["id"],
  branche: string,
  choix?: ChoixClone,
  modele?: string | null,
): Promise<Session> {
  const reponse = await fetchAuthentifie("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({
      repo,
      agent,
      branche,
      ...(choix && { choix }),
      ...(modele !== undefined ? { modele } : {}),
    }),
  });
  const corps = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    const erreur = new ErreurApi(corps?.detail ?? `lancement : HTTP ${reponse.status}`);
    erreur.session = corps?.session ?? null;
    erreur.clone = corps?.clone ?? null;
    throw erreur;
  }
  return corps as Session;
}

/** **Terminer** : `POST /api/sessions/{id}/terminer`, la session rendue avec son état final. */
export async function terminerSession(id: string): Promise<Session> {
  if (!ID_SESSION.test(id)) throw new ErreurApi(`session invalide : ${id}`);
  const reponse = await fetchAuthentifie(`/api/sessions/${encodeURIComponent(id)}/terminer`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  const corps = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    throw new ErreurApi(corps?.detail ?? `terminer : HTTP ${reponse.status}`);
  }
  return corps as Session;
}

/** Websocket du terminal en direct, sur le cockpit servi (le runtime vérifie son `Origin`). */
export function urlTerminal(id: string): string {
  if (!ID_SESSION.test(id)) throw new ErreurApi(`session invalide : ${id}`);
  const { protocol, host } = window.location;
  return `${protocol === "https:" ? "wss:" : "ws:"}//${host}/api/sessions/${encodeURIComponent(id)}/terminal`;
}

/** `GET /api/sessions/{id}/codespace` : l’identité du clone de la session (`direct` : lu en direct). */
export interface IdentiteCodespace {
  repo: string;
  /** `null` : HEAD détaché. */
  branche: string | null;
  /** HEAD court ; `null` sur un clone sans commit. */
  head: string | null;
  source: "direct";
}

/** Statut Git d’une entrée ; un dossier prend le plus fort de ce qu’il contient. */
export type StatutGit = "modifie" | "ajoute" | "non_suivi";

/** Une entrée d’un dossier du clone. `lien` : symlink qui sort du clone, jamais suivi. */
export interface EntreeCodespace {
  nom: string;
  type: "dossier" | "fichier" | "lien";
  /** Taille d’un fichier, en octets ; `null` sinon. */
  taille: number | null;
  /** Ignoré par `.gitignore`. */
  ignore: boolean;
  /** `null` : inchangé (ou ignoré). */
  statut: StatutGit | null;
}

/** `GET /api/sessions/{id}/codespace/arbre?chemin=` : les entrées d’un dossier, chargé à son ouverture. */
export interface ArbreCodespace {
  chemin: string;
  entrees: EntreeCodespace[];
}

/** `GET /api/sessions/{id}/codespace/fichier?chemin=` : `contenu` nul et `non_affiche` si binaire
 * ou plus de 1 Mo. */
export interface FichierCodespace {
  chemin: string;
  taille: number;
  contenu: string | null;
  non_affiche?: "binaire" | "trop_gros";
}

/** `GET /api/sessions/{id}/codespace/diff?chemin=` : versions HEAD et courante d’un fichier. `head`
 * nul : absent de HEAD (ajouté, non suivi). Binaire ou plus de 1 Mo : les deux nuls et `non_affiche`. */
export interface DiffCodespace {
  chemin: string;
  head: string | null;
  courant: string | null;
  non_affiche?: "binaire" | "trop_gros";
}

/** Lecture du codespace de la session `id` ; `chemin` est relatif au clone. */
export function lireCodespace<T>(
  id: string,
  suite: "" | "/arbre" | "/fichier" | "/diff",
  chemin?: string,
): Promise<T> {
  if (!ID_SESSION.test(id)) throw new ErreurApi(`session invalide : ${id}`);
  const requete = chemin === undefined ? "" : `?chemin=${encodeURIComponent(chemin)}`;
  return lire<T>(`/api/sessions/${encodeURIComponent(id)}/codespace${suite}${requete}`);
}
