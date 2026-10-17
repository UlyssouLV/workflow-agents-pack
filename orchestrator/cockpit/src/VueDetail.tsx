import { useState } from "react";
import type {
  Agent,
  Auth,
  Bug,
  ChoixClone,
  CloneSale,
  Detail,
  EtatCi,
  LienSession,
  Session,
  SessionsDuRepo,
  Version,
} from "./api";
import { ErreurApi, ID_SESSION, lancerSession } from "./api";
import {
  BadgeHumain,
  BadgeSession,
  BandeauAuth,
  Entete,
  LIBELLES_ETAT_SESSION,
  LibelleEtape,
  LiensChaine,
  dateHeure,
  heure,
  nomAffiche,
} from "./commun";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";

const LIBELLES_CI: Record<EtatCi, string> = {
  echec: "en échec",
  en_cours: "en cours",
  ok: "ok",
  aucune: "aucun check",
};

/** `/repos/<owner>/<name>` : tout l’état du repo, relu en direct à chaque rafraîchissement. */
export function VueDetail({ owner, name }: { owner: string; name: string }) {
  const chemin = `/api/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`;
  const { donnees, erreur } = useRafraichi<Detail>(chemin);
  const auth = useRafraichi<Auth>("/api/auth");
  const toutes = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);

  return (
    <main>
      <Entete />
      {auth.donnees && <BandeauAuth auth={auth.donnees} />}
      {erreur && <p className="erreur">{erreur}</p>}
      {donnees && <Contenu detail={donnees} sessions={toutes.donnees?.sessions ?? []} />}
      <Sessions chemin={`${chemin}/sessions`} agents={donnees?.agents ?? []} />
    </main>
  );
}

/** Sessions du repo, lues dans `jobs/` sans GitHub : affichées même quand le repo est en erreur. */
function Sessions({ chemin, agents }: { chemin: string; agents: Agent[] }) {
  const { donnees, erreur } = useRafraichi<SessionsDuRepo>(chemin, RAFRAICHISSEMENT_SESSION_MS);
  const nom = (id: Agent["id"]) => agents.find((a) => a.id === id)?.nom ?? id;

  return (
    <section aria-label="Sessions">
      <h2>Sessions</h2>
      {erreur && <p className="erreur">{erreur}</p>}
      {donnees &&
        (donnees.sessions.length === 0 ? (
          <p>Aucune session.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Agent</th>
                <th>Commande</th>
                <th>État</th>
                <th>Chaîne</th>
              </tr>
            </thead>
            <tbody>
              {donnees.sessions.map((s) => (
                <tr key={s.id}>
                  <td>
                    <a href={s.url}>{dateHeure(s.debut)}</a>
                  </td>
                  <td>{nom(s.agent)}</td>
                  <td>
                    <code>{s.commande}</code>
                  </td>
                  <td>{LIBELLES_ETAT_SESSION[s.etat]}</td>
                  <td>
                    <LiensChaine session={s} libelles={["précédente", "suivante"]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
    </section>
  );
}

function Contenu({ detail, sessions }: { detail: Detail; sessions: Session[] }) {
  const [agent, setAgent] = useState<Agent["id"]>(
    () => (detail.agents.find((a) => a.connecte) ?? detail.agents[0])?.id ?? "claude",
  );
  const [branche, setBranche] = useState(() => detail.branches.defaut);
  const [refus, setRefus] = useState<{ message: string; session: LienSession | null } | null>(null);
  // Clone sale au lancement : rien n’est lancé tant que l’utilisateur n’a pas choisi.
  const [sale, setSale] = useState<CloneSale | null>(null);

  const choisi = detail.agents.find((a) => a.id === agent);
  const travaille = sessions.find(
    (s) =>
      s.etat === "ouverte" &&
      s.activite === "travaille" &&
      s.repo.toLowerCase() !== detail.slug.toLowerCase(),
  );
  const raison = !choisi?.connecte
    ? "agent non connecté"
    : detail.session
      ? "session déjà ouverte sur ce repo"
      : travaille
        ? `une session travaille sur ${travaille.repo}`
        : null;

  const lancer = (choix?: ChoixClone) => {
    setRefus(null);
    setSale(null);
    lancerSession(detail.slug, agent, branche, choix).then(
      (session) => {
        // Page bâtie ici, pas l’URL de la réponse : on ne quitte pas le cockpit.
        if (ID_SESSION.test(session.id)) window.location.assign(`/sessions/${session.id}`);
      },
      (erreur: Error) => {
        if (erreur instanceof ErreurApi && erreur.clone) {
          setSale(erreur.clone);
        } else {
          setRefus({ message: erreur.message, session: erreur instanceof ErreurApi ? erreur.session : null });
        }
      },
    );
  };

  return (
    <>
      <h1>{nomAffiche(detail)}</h1>
      <p>
        <a href={detail.url}>{detail.url.replace("https://", "")}</a> · lu à {heure(detail.lu_a)}
      </p>
      {detail.erreur ? (
        <p className="erreur">{detail.erreur}</p>
      ) : (
        <>
          <p>
            Étape : <strong>{detail.etape?.libelle}</strong> {detail.humain_requis && <BadgeHumain />}
          </p>
          {detail.session && (
            <p>
              <BadgeSession session={detail.session} /> sur {detail.session.repo}
            </p>
          )}
          <p>
            <label>
              Agent{" "}
              <select value={agent} onChange={(e) => setAgent(e.target.value as Agent["id"])}>
                {detail.agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nom}
                    {!a.connecte && " (non connecté)"}
                  </option>
                ))}
              </select>
            </label>{" "}
            <label>
              Branche{" "}
              <select value={branche} onChange={(e) => setBranche(e.target.value)}>
                {detail.branches.proposees.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>{" "}
            <button type="button" disabled={raison !== null} title={raison ?? undefined} onClick={() => lancer()}>
              Nouvelle session
            </button>
            {raison && (
              <span className="raison">
                {raison}
                {detail.session && raison === "session déjà ouverte sur ce repo" && (
                  <>
                    {" "}
                    — <a href={detail.session.url}>voir la session ouverte</a>
                  </>
                )}
                {travaille && raison?.startsWith("une session travaille") && (
                  <>
                    {" "}
                    — <a href={travaille.url}>voir la session ouverte</a>
                  </>
                )}
              </span>
            )}
          </p>
          {refus && (
            <p role="alert" className="erreur">
              Lancement refusé : {refus.message}
              {refus.session && (
                <>
                  {" "}
                  — <a href={refus.session.url}>voir la session ouverte</a>
                </>
              )}
            </p>
          )}
          {sale && (
            <ChoixCloneSale clone={sale} choisir={(choix) => lancer(choix)} annuler={() => setSale(null)} />
          )}
          {detail.versions.map((v) => (
            <SectionVersion key={v.numero} version={v} />
          ))}
          <Bugs bugs={detail.bugs} />
        </>
      )}
    </>
  );
}

function SectionVersion({ version }: { version: Version }) {
  const nom = `#${version.numero} ${version.titre}`;
  const { pr } = version;
  return (
    <section aria-label={nom}>
      <h2>
        <a href={version.url}>{nom}</a>
      </h2>
      <p>
        Progression : {version.progression.completed}/{version.progression.total} · Étape :{" "}
        <LibelleEtape etape={version.etape} />
      </p>
      {version.signaux.length > 0 && (
        <p>Signaux : {version.signaux.map((s) => s.libelle).join(", ")}</p>
      )}
      <table aria-label="Enfants">
        <thead>
          <tr>
            <th>Enfant</th>
            <th>État</th>
            <th>Labels</th>
          </tr>
        </thead>
        <tbody>
          {version.enfants.map((e) => (
            <tr key={e.numero}>
              <td>
                <a href={e.url}>
                  #{e.numero} {e.titre}
                </a>
              </td>
              <td>
                {e.ouvert ? "ouvert" : "fermé"}
                {e.bloque && ", bloqué"}
              </td>
              <td>{e.labels.join(", ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {pr === null ? (
        <p>Aucune PR de version (corps contenant « Fixes #{version.numero} »).</p>
      ) : (
        <>
          <p>
            <a href={pr.url}>
              PR #{pr.numero} {pr.titre}
            </a>
            {pr.brouillon && " (brouillon)"} · CI : {LIBELLES_CI[pr.ci]}
          </p>
          {pr.checks.length > 0 && (
            <ul>
              {pr.checks.map((c) => (
                <li key={c.nom} aria-label={c.nom}>
                  {c.url ? <a href={c.url}>{c.nom}</a> : c.nom} : {LIBELLES_CI[c.etat]}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}

/** Clone sale : les changements laissés par une session précédente, à reprendre ou jeter. */
function ChoixCloneSale({
  clone,
  choisir,
  annuler,
}: {
  clone: CloneSale;
  choisir: (choix: ChoixClone) => void;
  annuler: () => void;
}) {
  return (
    <section role="dialog" aria-labelledby="titre-clone-sale" className="clone-sale">
      <h2 id="titre-clone-sale">Le clone a des changements non commités</h2>
      <p>
        Une session précédente les a laissés sur <code>{clone.branche}</code>. <strong>Reprendre</strong> lance
        sur cette branche, sans la changer ; <strong>Jeter</strong> les garde dans <code>abandon.patch</code> de
        la session, remet le clone à zéro puis passe sur la branche choisie.
      </p>
      <ul aria-label="Fichiers modifiés">
        {clone.fichiers.map((f) => (
          <li key={f.chemin}>
            <code>
              {f.statut} {f.chemin}
            </code>
          </li>
        ))}
      </ul>
      <pre aria-label="Diff">{clone.diff}</pre>
      <p>
        <button type="button" onClick={() => choisir("reprendre")}>
          Reprendre
        </button>{" "}
        <button type="button" onClick={() => choisir("jeter")}>
          Jeter
        </button>{" "}
        <button type="button" onClick={annuler}>
          Annuler
        </button>
      </p>
    </section>
  );
}

function Bugs({ bugs }: { bugs: Bug[] }) {
  return (
    <section aria-label="Bugs ouverts">
      <h2>Bugs ouverts</h2>
      {bugs.length === 0 ? (
        <p>Aucun.</p>
      ) : (
        <ul>
          {bugs.map((b) => (
            <li key={b.numero}>
              <a href={b.url}>
                #{b.numero} {b.titre}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
