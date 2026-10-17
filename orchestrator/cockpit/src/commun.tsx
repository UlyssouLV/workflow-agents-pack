import type { Agent, Auth, Etape, EtatSession, Repo } from "./api";

const MESSAGES_AUTH: Partial<Record<Auth["etat"], string>> = {
  sans_token: "GitHub non connecté",
  token_refuse: "Token refusé par GitHub",
  injoignable: "GitHub injoignable",
};

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

export const LIBELLES_ETAT_SESSION: Record<EtatSession, string> = {
  ouverte: "Ouverte",
  terminée: "Terminée",
  échouée: "Échouée",
  interrompue: "Interrompue",
};

/** Date et heure, au fuseau du navigateur, sans les secondes. */
export function dateHeure(iso: string): string {
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}
