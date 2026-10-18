import { useEffect, useRef, useState } from "react";
import type {
  ActiviteSession,
  Agent,
  Auth,
  Etape,
  EtatSession,
  LienSession,
  Liste,
  Repo,
  Session,
  SessionsDuRepo,
} from "./api";
import { ID_SESSION } from "./api";
import { demanderPermissionNotifications, notifierStops } from "./notifications";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";

const TITRE_ONGLET = "Cockpit wap-runtime";

const MESSAGES_AUTH: Partial<Record<Auth["etat"], string>> = {
  sans_token: "GitHub non connecté",
  token_refuse: "Token refusé par GitHub",
  injoignable: "GitHub injoignable",
};

/** En-tête du cockpit : liste des repos, page Sessions, compteur de réponses attendues. */
export function Entete() {
  const { donnees } = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);
  const liste = useRafraichi<Liste>("/api/repos");
  const n = (donnees?.sessions ?? []).filter((s) => s.etat === "ouverte" && s.activite === "attend").length;
  const [permission, setPermission] = useState<NotificationPermission | null>(
    typeof Notification === "undefined" ? null : Notification.permission,
  );
  const vus = useRef(new Map<string, string>());
  useEffect(() => {
    document.title = n > 0 ? `(${n}) ${TITRE_ONGLET}` : TITRE_ONGLET;
  }, [n]);
  useEffect(() => {
    void demanderPermissionNotifications().then((p) => p && setPermission(p));
  }, []);
  useEffect(() => {
    if (permission !== "granted" || !liste.donnees) return;
    notifierStops(liste.donnees.repos, vus.current);
  }, [permission, liste.donnees]);
  return (
    <header>
      <nav>
        <a href="/">Cockpit</a>
        {" · "}
        <a href="/sessions">Sessions</a>
        {" · "}
        <a href="/sessions">
          {n} réponse(s) attendue(s)
        </a>
      </nav>
    </header>
  );
}

/** Bandeau global quand l’instance ne peut pas lire GitHub. */
export function BandeauAuth({ auth }: { auth: Auth }) {
  if (auth.etat === "connecte") {
    return <p className="compte">Connecté à GitHub : {auth.compte}</p>;
  }
  return (
    <p role="alert" className="bandeau">
      {MESSAGES_AUTH[auth.etat]} : lancez <code>sudo wap-runtime auth</code> sur l’hôte.
    </p>
  );
}

/** Encart Agents : Claude Code / Cursor connectés ou non, avec la commande à lancer sur l’hôte. */
export function EncartAgents({ agents }: { agents: Agent[] }) {
  return (
    <section aria-labelledby="titre-agents" className="agents">
      <h2 id="titre-agents">Agents</h2>
      <ul>
        {agents.map((agent) => (
          <li key={agent.id} className={agent.connecte ? undefined : "non-connecte"}>
            {agent.nom} : {agent.connecte ? "Connecté" : "Non connecté"}
            {!agent.connecte && (
              <>
                {" "}
                — lancez <code>{agent.commande}</code> sur l’hôte
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function BadgeHumain() {
  return <span className="badge">Intervention humaine requise</span>;
}

export function BadgePilote() {
  return <span className="badge pilote">Pilote</span>;
}

export function BadgePause() {
  return <span className="badge pause">En pause</span>;
}

export function LibelleEtape({ etape }: { etape: Etape | null }) {
  if (etape === null) return null;
  return (
    <>
      {etape.libelle} {etape.humain && <BadgeHumain />}
    </>
  );
}

export function nomAffiche(repo: Pick<Repo, "slug" | "nom">): string {
  return repo.nom ?? repo.slug;
}

export function heure(iso: string): string {
  return new Date(iso).toLocaleTimeString("fr-FR");
}

export const LIBELLES_ACTIVITE: Record<ActiviteSession, string> = {
  travaille: "Travaille",
  attend: "Réponse attendue",
  inconnue: "Inconnue",
};

/** Badge de la vue liste (et détail) : activité inconnue → Session en cours. */
export function libelleBadgeSession(activite?: ActiviteSession | null): string {
  if (activite === "travaille") return LIBELLES_ACTIVITE.travaille;
  if (activite === "attend") return LIBELLES_ACTIVITE.attend;
  return "Session en cours";
}

export function libelleActivite(session: Pick<Session, "activite" | "skill">): string {
  const base = LIBELLES_ACTIVITE[session.activite] ?? LIBELLES_ACTIVITE.inconnue;
  return session.activite === "attend" && session.skill ? `${base} — ${session.skill}` : base;
}

export function BadgeSession({ session }: { session: LienSession }) {
  return (
    <a className="badge session" href={session.url}>
      {libelleBadgeSession(session.activite)}
    </a>
  );
}

export const LIBELLES_ETAT_SESSION: Record<EtatSession, string> = {
  ouverte: "Ouverte",
  terminée: "Terminée",
  échouée: "Échouée",
  interrompue: "Interrompue",
  enchaînée: "Enchaînée",
};

/** `/sessions/<id>` d’une voisine de la chaîne ; seul un identifiant valide bâtit l’URL. */
export function lienSession(id: string | null): string | null {
  return id && ID_SESSION.test(id) ? `/sessions/${id}` : null;
}

/** Liens vers la précédente et la suivante d’une session enchaînée ; rien hors chaîne. */
export function LiensChaine({
  session,
  libelles,
}: {
  session: Pick<Session, "precedente" | "suivante">;
  libelles: [precedente: string, suivante: string];
}) {
  const [precedente, suivante] = [lienSession(session.precedente), lienSession(session.suivante)];
  return (
    <>
      {precedente && <a href={precedente}>{libelles[0]}</a>}
      {precedente && suivante && " · "}
      {suivante && <a href={suivante}>{libelles[1]}</a>}
    </>
  );
}

/** Date et heure, au fuseau du navigateur, sans les secondes. */
export function dateHeure(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}
