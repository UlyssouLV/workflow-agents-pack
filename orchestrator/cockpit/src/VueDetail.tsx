import type { Auth, Bug, Detail, EtatCi, Version } from "./api";
import { BadgeHumain, BandeauAuth, LibelleEtape, heure, nomAffiche } from "./commun";
import { useRafraichi } from "./rafraichi";

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

  return (
    <main>
      <p>
        <a href="/">← Tous les repos</a>
      </p>
      {auth.donnees && <BandeauAuth auth={auth.donnees} />}
      {erreur && <p className="erreur">{erreur}</p>}
      {donnees && <Contenu detail={donnees} />}
    </main>
  );
}

function Contenu({ detail }: { detail: Detail }) {
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
