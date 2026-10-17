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

export async function lire<T>(chemin: string): Promise<T> {
  const reponse = await fetch(chemin, { headers: { Accept: "application/json" } });
  if (!reponse.ok) {
    // FastAPI rend `{"detail": "<message>"}` (404 : repo absent du registry).
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `${chemin} : HTTP ${reponse.status}`);
  }
  return (await reponse.json()) as T;
}

/** `GET /api/sessions` et `GET /api/repos/{owner}/{name}/sessions` : plus récentes d’abord. */
export interface SessionsDuRepo {
  sessions: Session[];
}

/** `GET /api/sessions/{id}/terminal.cast` : le terminal enregistré (asciinema v2), en texte. */
export async function lireEnregistrement(id: string): Promise<string> {
  if (!ID_SESSION.test(id)) throw new ErreurApi(`session invalide : ${id}`);
  const chemin = `/api/sessions/${encodeURIComponent(id)}/terminal.cast`;
  const reponse = await fetch(chemin);
  if (!reponse.ok) {
    const corps = await reponse.json().catch(() => null);
    throw new ErreurApi(corps?.detail ?? `${chemin} : HTTP ${reponse.status}`);
  }
  return reponse.text();
}

/** `POST /api/sessions` ; le navigateur y joint l’en-tête `Origin` que le runtime vérifie. */
export async function lancerSession(
  repo: string,
  agent: Agent["id"],
  branche: string,
  choix?: ChoixClone,
): Promise<Session> {
  const reponse = await fetch("/api/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ repo, agent, branche, ...(choix && { choix }) }),
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
  const reponse = await fetch(`/api/sessions/${encodeURIComponent(id)}/terminer`, {
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
