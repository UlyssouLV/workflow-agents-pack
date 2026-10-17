import type { Agent, SessionsDuRepo } from "./api";
import { Entete, LIBELLES_ETAT_SESSION } from "./commun";
import { useRafraichi } from "./rafraichi";
import { RAFRAICHISSEMENT_SESSION_MS } from "./VueSession";

/** `/sessions` : toutes les sessions de l’instance, plus récentes d’abord. */
export function VueSessions() {
  const { donnees, erreur } = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);
  const agents = useRafraichi<{ agents: Agent[] }>("/api/agents");
  const nom = (id: Agent["id"]) => agents.donnees?.agents.find((a) => a.id === id)?.nom ?? id;

  return (
    <main>
      <Entete />
      <h1>Sessions</h1>
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
                <th>Branche</th>
                <th>Titre</th>
                <th>État</th>
              </tr>
            </thead>
            <tbody>
              {donnees.sessions.map((s) => (
                <tr key={s.id}>
                  <td>{s.repo}</td>
                  <td>{nom(s.agent)}</td>
                  <td>{s.branche ?? "—"}</td>
                  <td>
                    <a href={s.url}>{s.titre}</a>
                  </td>
                  <td>{LIBELLES_ETAT_SESSION[s.etat]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
    </main>
  );
}
