import type { Liste, Repo } from "./api";
import { BadgeHumain, BandeauAuth, heure, nomAffiche } from "./commun";
import { useRafraichi } from "./rafraichi";

/** `/` : une ligne par repo lié, ceux qui attendent quelqu’un en tête. */
export function VueListe() {
  const { donnees, erreur } = useRafraichi<Liste>("/api/repos");

  return (
    <main>
      <h1>Cockpit</h1>
      {erreur && <p className="erreur">Lecture impossible : {erreur}</p>}
      {donnees && <Contenu liste={donnees} />}
    </main>
  );
}

function Contenu({ liste }: { liste: Liste }) {
  return (
    <>
      <BandeauAuth auth={liste.auth} />
      {liste.erreur && <p className="erreur">Registry : {liste.erreur}</p>}
      {!liste.erreur && liste.repos.length === 0 && (
        <p>
          Aucun repo lié. Ajoutez-en un sur l’hôte : <code>sudo wap-runtime repo add owner/name</code>
        </p>
      )}
      {liste.repos.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Repo</th>
              <th>Version ouverte</th>
              <th>Progression</th>
              <th>Étape</th>
              <th>Lu à</th>
            </tr>
          </thead>
          <tbody>
            {trier(liste.repos).map((repo) => (
              <Ligne key={repo.slug} repo={repo} />
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

/** « Humain requis » d’abord ; sinon l’ordre du registry. */
function trier(repos: Repo[]): Repo[] {
  return [...repos].sort((a, b) => Number(b.humain_requis) - Number(a.humain_requis));
}

function Ligne({ repo }: { repo: Repo }) {
  return (
    <tr className={repo.erreur ? "en-erreur" : undefined}>
      <td>
        <a href={`/repos/${repo.slug}`}>{nomAffiche(repo)}</a>
      </td>
      {repo.erreur ? (
        <td colSpan={3} className="erreur">
          {repo.erreur}
        </td>
      ) : (
        <>
          <td>
            {repo.versions.map((v) => (
              <div key={v.numero}>
                <a href={v.url}>
                  #{v.numero} {v.titre}
                </a>
              </div>
            ))}
          </td>
          <td>
            {repo.versions.map((v) => (
              <div key={v.numero}>
                {v.progression.completed}/{v.progression.total}
              </div>
            ))}
          </td>
          <td>
            {repo.etape?.libelle} {repo.humain_requis && <BadgeHumain />}
          </td>
        </>
      )}
      <td>{heure(repo.lu_a)}</td>
    </tr>
  );
}
