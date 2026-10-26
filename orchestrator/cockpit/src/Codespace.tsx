import { useEffect, useRef, useState } from "react";
import type { ArbreCodespace, EntreeCodespace, FichierCodespace, IdentiteCodespace } from "./api";
import { lireCodespace } from "./api";
import { monaco } from "./monaco";

/** Un dossier chargé (ses entrées), ou le refus du runtime. */
type Dossier = EntreeCodespace[] | { erreur: string };
/** Un fichier lu, ou le refus du runtime. */
type Fichier = FichierCodespace | { erreur: string };

/** Vue du codespace d’une session (ADR 0014), en lecture seule : l’identité du clone, son
 * arborescence chargée dossier par dossier, et les fichiers ouverts en onglets dans Monaco. */
export function Codespace({ id }: { id: string }) {
  const [identite, setIdentite] = useState<IdentiteCodespace | { erreur: string } | null>(null);
  const [dossiers, setDossiers] = useState<Record<string, Dossier>>({});
  const [deplies, setDeplies] = useState<ReadonlySet<string>>(new Set());
  const [ouverts, setOuverts] = useState<string[]>([]);
  const [actif, setActif] = useState<string | null>(null);
  const [fichiers, setFichiers] = useState<Record<string, Fichier>>({});

  const charger = (chemin: string) =>
    lireCodespace<ArbreCodespace>(id, "/arbre", chemin).then(
      (arbre) => setDossiers((d) => ({ ...d, [chemin]: arbre.entrees })),
      (erreur: Error) => setDossiers((d) => ({ ...d, [chemin]: { erreur: erreur.message } })),
    );

  useEffect(() => {
    lireCodespace<IdentiteCodespace>(id, "").then(setIdentite, (erreur: Error) =>
      setIdentite({ erreur: erreur.message }),
    );
    charger("");
  }, [id]);

  const basculer = (chemin: string) => {
    const suivants = new Set(deplies);
    if (suivants.delete(chemin)) {
      setDeplies(suivants);
      return;
    }
    setDeplies(suivants.add(chemin));
    if (!(chemin in dossiers)) charger(chemin);
  };

  const ouvrir = (chemin: string) => {
    setOuverts((o) => (o.includes(chemin) ? o : [...o, chemin]));
    setActif(chemin);
    lireCodespace<FichierCodespace>(id, "/fichier", chemin).then(
      (fichier) => setFichiers((f) => ({ ...f, [chemin]: fichier })),
      (erreur: Error) => setFichiers((f) => ({ ...f, [chemin]: { erreur: erreur.message } })),
    );
  };

  const fermer = (chemin: string) => {
    const restants = ouverts.filter((o) => o !== chemin);
    setOuverts(restants);
    if (actif === chemin) {
      const rang = ouverts.indexOf(chemin);
      setActif(restants[Math.min(rang, restants.length - 1)] ?? null);
    }
  };

  return (
    <div className="codespace">
      <EnteteCodespace identite={identite} />
      <div className="codespace-corps">
        <ul role="tree" aria-label="Fichiers du codespace" className="arbre">
          <Entrees chemin="" dossiers={dossiers} deplies={deplies} basculer={basculer} ouvrir={ouvrir} />
        </ul>
        <section aria-label="Fichier" className="codespace-fichier">
          {ouverts.length > 0 && (
            <div role="tablist" aria-label="Fichiers ouverts" className="onglets-fichiers">
              {ouverts.map((chemin) => (
                <span key={chemin} className="onglet-fichier">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={chemin === actif}
                    title={chemin}
                    onClick={() => setActif(chemin)}
                  >
                    {nomDe(chemin)}
                  </button>
                  <button type="button" aria-label={`Fermer ${nomDe(chemin)}`} onClick={() => fermer(chemin)}>
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
          {actif !== null && <EtatFichier fichier={fichiers[actif]} />}
          {/* Gardé monté d’un fichier à l’autre : seul le modèle change. */}
          {actif !== null && <EditeurMonaco fichier={texte(fichiers[actif])} />}
        </section>
      </div>
    </div>
  );
}

function EnteteCodespace({ identite }: { identite: IdentiteCodespace | { erreur: string } | null }) {
  if (identite === null) return <p className="etat-terminal">Lecture du codespace…</p>;
  if ("erreur" in identite) return <p className="erreur">{identite.erreur}</p>;
  const { repo, branche, head } = identite;
  return (
    <p role="group" aria-label="Identité du codespace" className="identite-codespace">
      <strong>{repo}</strong> · branche{" "}
      {branche ? (
        <a href={`https://github.com/${repo}/tree/${branche.split("/").map(encodeURIComponent).join("/")}`}>
          {branche}
        </a>
      ) : (
        "HEAD détaché"
      )}{" "}
      · {head ? <code>{head}</code> : "aucun commit"}
    </p>
  );
}

interface PropsEntrees {
  chemin: string;
  dossiers: Record<string, Dossier>;
  deplies: ReadonlySet<string>;
  basculer: (chemin: string) => void;
  ouvrir: (chemin: string) => void;
}

/** Les entrées du dossier `chemin`, une fois chargé ; un dossier déplié montre les siennes. */
function Entrees({ chemin, dossiers, deplies, basculer, ouvrir }: PropsEntrees) {
  const dossier = dossiers[chemin];
  if (dossier === undefined) return <li className="etat-terminal">Chargement…</li>;
  if ("erreur" in dossier)
    return (
      <li role="alert" className="erreur">
        {dossier.erreur}
      </li>
    );
  return dossier.map((entree) => {
    const complet = chemin ? `${chemin}/${entree.nom}` : entree.nom;
    const deplie = deplies.has(complet);
    return (
      <li
        key={entree.nom}
        role="treeitem"
        aria-label={entree.nom}
        aria-expanded={entree.type === "dossier" ? deplie : undefined}
        className={entree.ignore ? "ignore" : undefined}
      >
        {entree.type === "lien" ? (
          <>
            <span>{entree.nom}</span> <span className="raison">lien hors du clone</span>
          </>
        ) : (
          <button
            type="button"
            className={entree.type}
            onClick={() => (entree.type === "dossier" ? basculer(complet) : ouvrir(complet))}
          >
            {entree.nom}
          </button>
        )}
        {deplie && (
          <ul role="group">
            <Entrees chemin={complet} dossiers={dossiers} deplies={deplies} basculer={basculer} ouvrir={ouvrir} />
          </ul>
        )}
      </li>
    );
  });
}

/** Le fichier à montrer dans l’éditeur, s’il est lu et affichable. */
function texte(fichier: Fichier | undefined): { chemin: string; contenu: string } | null {
  if (fichier === undefined || "erreur" in fichier || fichier.contenu === null) return null;
  return { chemin: fichier.chemin, contenu: fichier.contenu };
}

/** Ce qui remplace l’éditeur : lecture en cours, refus, ou « non affiché ». */
function EtatFichier({ fichier }: { fichier: Fichier | undefined }) {
  if (fichier === undefined) return <p className="etat-terminal">Lecture du fichier…</p>;
  if ("erreur" in fichier) return <p className="erreur">{fichier.erreur}</p>;
  if (fichier.contenu === null)
    return (
      <p className="etat-terminal">
        {`${fichier.non_affiche === "trop_gros" ? "Fichier de plus de 1 Mo" : "Fichier binaire"} : non affiché (${taille(fichier.taille)})`}
      </p>
    );
  return null;
}

/** Monaco en lecture seule, caché sans fichier à montrer ; le langage (coloration) se déduit du
 * nom du fichier. */
function EditeurMonaco({ fichier }: { fichier: { chemin: string; contenu: string } | null }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const editeur = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    editeur.current = monaco.editor.create(conteneur.current!, {
      readOnly: true,
      domReadOnly: true,
      automaticLayout: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
    });
    return () => editeur.current?.dispose();
  }, []);

  const chemin = fichier?.chemin;
  const contenu = fichier?.contenu;
  useEffect(() => {
    if (chemin === undefined || contenu === undefined) {
      editeur.current?.setModel(null);
      return;
    }
    const modele = monaco.editor.createModel(contenu, undefined, monaco.Uri.file(chemin));
    editeur.current?.setModel(modele);
    return () => modele.dispose();
  }, [chemin, contenu]);

  return <div className="editeur" ref={conteneur} hidden={fichier === null} />;
}

function nomDe(chemin: string): string {
  return chemin.slice(chemin.lastIndexOf("/") + 1);
}

/** Taille lisible : octets, Ko ou Mo (base 1024, une décimale). */
export function taille(octets: number): string {
  const decimale = (n: number) => n.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  if (octets < 1024) return `${octets} o`;
  if (octets < 1024 * 1024) return `${decimale(octets / 1024)} Ko`;
  return `${decimale(octets / (1024 * 1024))} Mo`;
}
