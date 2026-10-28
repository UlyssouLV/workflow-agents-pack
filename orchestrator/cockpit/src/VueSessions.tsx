import type { Agent, SessionsDuRepo } from "./api";
import { ContenuPage, Coque, EnTetePage } from "./Coque";
import { LIBELLES_ETAT_SESSION, libelleActivite, libelleModele } from "./commun";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";

/** `/sessions` : toutes les sessions de l’instance, plus récentes d’abord. */
export function VueSessions() {
  const { donnees, erreur } = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);
  const agents = useRafraichi<{ agents: Agent[] }>("/api/agents");
  const nom = (id: Agent["id"]) => agents.donnees?.agents.find((a) => a.id === id)?.nom ?? id;
  const avecModele = (donnees?.sessions ?? []).some((s) => s.agent === "cursor");

  return (
    <Coque courant="sessions">
      <EnTetePage titre="Sessions" />
      <ContenuPage>
        {erreur && <p className="erreur">{erreur}</p>}
        {donnees &&
          (donnees.sessions.length === 0 ? (
            <p>Aucune session.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Repo</th>
                  <th>Agent</th>
                  {avecModele && <th>Modèle</th>}
                  <th>Branche</th>
                  <th>Titre</th>
                  <th>État</th>
                  <th>Activité</th>
                </tr>
              </thead>
              <tbody>
                {donnees.sessions.map((s) => (
                  <tr key={s.id}>
                    <td>{s.repo}</td>
                    <td>{nom(s.agent)}</td>
                    {avecModele && <td>{libelleModele(s)}</td>}
                    <td>{s.branche ?? "—"}</td>
                    <td>
                      <a href={s.url}>{s.titre}</a>
                    </td>
                    <td>{LIBELLES_ETAT_SESSION[s.etat]}</td>
                    <td>{s.etat === "ouverte" ? libelleActivite(s) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ))}
      </ContenuPage>
    </Coque>
  );
}
