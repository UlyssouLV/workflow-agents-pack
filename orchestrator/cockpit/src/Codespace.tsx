import { useEffect, useRef, useState } from "react";
import type {
  AbonnementCodespace,
  ArbreCodespace,
  DiffCodespace,
  EntreeCodespace,
  EtatInstantane,
  EvenementCodespace,
  FichierCodespace,
  IdentiteCodespace,
  StatutGit,
} from "./api";
import { lireCodespace, urlEvenementsCodespace } from "./api";
import { dateHeure } from "./commun";
import { monaco } from "./monaco";

/** Un dossier chargé (ses entrées), ou le refus du runtime. */
type Dossier = EntreeCodespace[] | { erreur: string };
/** Un fichier lu, ou le refus du runtime. */
type Fichier = FichierCodespace | { erreur: string };
/** Un diff lu, ou le refus du runtime. */
type Diff = DiffCodespace | { erreur: string };

/** Marqueur d’un fichier dans l’arbre, comme VS Code : lettre et libellé. */
const MARQUEURS: Record<StatutGit, [string, string]> = {
  modifie: ["M", "Modifié"],
  ajoute: ["A", "Ajouté"],
  non_suivi: ["U", "Non suivi"],
};

/** Sans surveillance du disque (indisponible, websocket coupé) : la vue est relue à ce rythme. */
export const POLLING_CODESPACE_MS = 10_000;

/** Vue du codespace d’une session (ADR 0014), en lecture seule : l’identité du clone, son
 * arborescence chargée dossier par dossier avec les marqueurs Git, et les fichiers ouverts en
 * onglets dans Monaco ; un fichier changé s’ouvre aussi en diff avec HEAD.
 *
 * En direct, comme VS Code : tant qu’elle est `visible`, la vue s’abonne aux dossiers dépliés et
 * au fichier ouvert, et les relit à chaque changement poussé par le runner ; sans surveillance,
 * elle se relit toutes les `POLLING_CODESPACE_MS`.
 *
 * Session close (`enDirect` faux) : la même vue, lue dans l’instantané de fin de session, sans
 * surveillance ; un bandeau daté, et les entrées ignorées et `.git/` grisées « non conservé ». */
export function Codespace({ id, visible = true, enDirect = true }: { id: string; visible?: boolean; enDirect?: boolean }) {
  const [identite, setIdentite] = useState<IdentiteCodespace | { erreur: string } | null>(null);
  const [dossiers, setDossiers] = useState<Record<string, Dossier>>({});
  const [deplies, setDeplies] = useState<ReadonlySet<string>>(new Set());
  const [ouverts, setOuverts] = useState<string[]>([]);
  const [actif, setActif] = useState<string | null>(null);
  const [fichiers, setFichiers] = useState<Record<string, Fichier>>({});
  /** Statut Git de chaque fichier ouvert, tel que l’arbre le montrait à son ouverture. */
  const [statuts, setStatuts] = useState<Record<string, StatutGit | null>>({});
  const [enDiff, setEnDiff] = useState<ReadonlySet<string>>(new Set());
  const [diffs, setDiffs] = useState<Record<string, Diff>>({});

  const lireIdentite = () =>
    void lireCodespace<IdentiteCodespace>(id, "").then(setIdentite, (erreur: Error) =>
      setIdentite({ erreur: erreur.message }),
    );

  const charger = (chemin: string) =>
    void lireCodespace<ArbreCodespace>(id, "/arbre", chemin).then(
      (arbre) => setDossiers((d) => ({ ...d, [chemin]: arbre.entrees })),
      (erreur: Error) => setDossiers((d) => ({ ...d, [chemin]: { erreur: erreur.message } })),
    );

  const lireFichier = (chemin: string) =>
    void lireCodespace<FichierCodespace>(id, "/fichier", chemin).then(
      (fichier) => setFichiers((f) => ({ ...f, [chemin]: fichier })),
      (erreur: Error) => setFichiers((f) => ({ ...f, [chemin]: { erreur: erreur.message } })),
    );

  const lireDiff = (chemin: string) =>
    void lireCodespace<DiffCodespace>(id, "/diff", chemin).then(
      (diff) => setDiffs((d) => ({ ...d, [chemin]: diff })),
      (erreur: Error) => setDiffs((d) => ({ ...d, [chemin]: { erreur: erreur.message } })),
    );

  useEffect(() => {
    lireIdentite();
    charger("");
  }, [id]);

  const basculer = (chemin: string) => {
    const suivants = new Set(deplies);
    if (suivants.delete(chemin)) {
      setDeplies(suivants);
      return;
    }
    setDeplies(suivants.add(chemin));
    // Non surveillés tant que repliés : le dossier et ses sous-dossiers dépliés sont relus.
    for (const dossier of dossiersVisibles(suivants)) if (contient(chemin, dossier)) charger(dossier);
  };

  const ouvrir = (chemin: string, statut: StatutGit | null) => {
    setStatuts((s) => ({ ...s, [chemin]: statut }));
    setOuverts((o) => (o.includes(chemin) ? o : [...o, chemin]));
    setActif(chemin);
    lireFichier(chemin);
  };

  /** Un onglet repris : seul le fichier actif est surveillé, celui-ci a pu changer depuis. */
  const activer = (chemin: string) => {
    setActif(chemin);
    lireFichier(chemin);
    if (enDiff.has(chemin)) lireDiff(chemin);
  };

  const basculerDiff = (chemin: string) => {
    const suivants = new Set(enDiff);
    if (suivants.delete(chemin)) {
      setEnDiff(suivants);
      return;
    }
    setEnDiff(suivants.add(chemin));
    lireDiff(chemin);
  };

  const visibles = dossiersVisibles(deplies);
  const abonnement: AbonnementCodespace = { dossiers: visibles, fichier: actif };
  // Lu par le websocket au moment d’un événement : la vue telle qu’elle est alors.
  const vue = useRef({ abonnement, diff: false });
  vue.current = { abonnement, diff: actif !== null && enDiff.has(actif) };

  /** Relit ce qu’un changement touche ; un changement d’en-tête (commit, branche) change aussi
   * les marqueurs et le diff : tout ce qui est montré est relu. */
  const relire = (evenement: { dossiers: string[]; fichier: boolean; entete: boolean }) => {
    const { abonnement: courant, diff } = vue.current;
    if (evenement.entete) lireIdentite();
    for (const dossier of courant.dossiers)
      if (evenement.entete || evenement.dossiers.includes(dossier)) charger(dossier);
    if (courant.fichier !== null && (evenement.fichier || evenement.entete)) {
      lireFichier(courant.fichier);
      if (diff) lireDiff(courant.fichier);
    }
  };

  const socket = useRef<WebSocket | null>(null);
  const dejaVisible = useRef(false);
  useEffect(() => {
    if (!visible || !enDirect) return;
    const tout = { dossiers: [], fichier: true, entete: true };
    // De retour sur l’onglet : rien n’a été surveillé entre-temps.
    if (dejaVisible.current) relire(tout);
    dejaVisible.current = true;
    let polling: ReturnType<typeof setInterval> | undefined;
    const sonder = () => {
      polling ??= setInterval(() => relire(tout), POLLING_CODESPACE_MS);
    };
    const ws = new WebSocket(urlEvenementsCodespace(id));
    socket.current = ws;
    ws.onopen = () => ws.send(JSON.stringify(vue.current.abonnement));
    ws.onmessage = (message: MessageEvent) => {
      const evenement = JSON.parse(String(message.data)) as EvenementCodespace;
      if ("surveillance" in evenement) sonder();
      else relire(evenement);
    };
    ws.onclose = sonder;
    return () => {
      ws.onclose = null;
      ws.close();
      socket.current = null;
      clearInterval(polling);
    };
  }, [id, visible, enDirect]);

  const cle = JSON.stringify(abonnement);
  useEffect(() => {
    const ws = socket.current;
    if (ws?.readyState === WebSocket.OPEN) ws.send(cle);
  }, [cle]);

  const fermer = (chemin: string) => {
    const restants = ouverts.filter((o) => o !== chemin);
    if (enDiff.has(chemin)) setEnDiff(new Set([...enDiff].filter((c) => c !== chemin)));
    setOuverts(restants);
    if (actif === chemin) {
      const rang = ouverts.indexOf(chemin);
      setActif(restants[Math.min(rang, restants.length - 1)] ?? null);
    }
  };

  const diffActif = actif !== null && enDiff.has(actif);
  const instantane = identite !== null && !("erreur" in identite) && identite.source === "instantane" ? identite.instantane : null;

  return (
    <div className="codespace">
      {instantane?.etat === "present" && (
        <p role="status" className="bandeau-instantane">
          Instantané de fin de session — {dateHeure(instantane.pris_le)}
        </p>
      )}
      <EnteteCodespace identite={identite} />
      {instantane && instantane.etat !== "present" ? (
        <p role="status" className="etat-terminal">
          {sansInstantane(instantane)}
        </p>
      ) : (
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
                      onClick={() => activer(chemin)}
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
            {actif !== null && statuts[actif] && (
              <button type="button" className="bouton-diff" aria-pressed={diffActif} onClick={() => basculerDiff(actif)}>
                Diff avec HEAD
              </button>
            )}
            {actif !== null && (diffActif ? <EtatDiff diff={diffs[actif]} /> : <EtatFichier fichier={fichiers[actif]} />)}
            {/* Gardé monté d’un fichier à l’autre : seul le modèle change. */}
            {actif !== null && <EditeurMonaco fichier={diffActif ? null : texte(fichiers[actif])} />}
            {diffActif && <EditeurDiff diff={versions(diffs[actif])} />}
          </section>
        </div>
      )}
    </div>
  );
}

/** Pourquoi une session close n’a pas d’instantané à montrer. */
function sansInstantane(instantane: Exclude<EtatInstantane, { etat: "present" }>): string {
  if (instantane.etat === "absent") return "Pas d’instantané (session antérieure à la 0.8.0)";
  if (instantane.etat === "perdu") return "Instantané perdu : le clone a été supprimé ou recloné depuis";
  return `Instantané non pris : ${instantane.erreur}`;
}

function EnteteCodespace({ identite }: { identite: IdentiteCodespace | { erreur: string } | null }) {
  if (identite === null) return <p className="etat-terminal">Lecture du codespace…</p>;
  if ("erreur" in identite) return <p className="erreur">{identite.erreur}</p>;
  const { repo, branche, head } = identite;
  return (
    <p role="group" aria-label="Identité du codespace" className="identite-codespace">
      <strong>{repo}</strong> · branche{" "}
      {branche ? (
        <a
          href={`https://github.com/${repo}/tree/${branche.split("/").map(encodeURIComponent).join("/")}`}
          target="_blank"
          rel="noopener noreferrer"
        >
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
  ouvrir: (chemin: string, statut: StatutGit | null) => void;
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
        className={
          [entree.ignore && "ignore", entree.non_conserve && "non-conserve", entree.statut && `statut-${entree.statut}`]
            .filter(Boolean)
            .join(" ") || undefined
        }
      >
        {entree.non_conserve ? (
          <>
            <span>{entree.nom}</span> <span className="raison">non conservé</span>
          </>
        ) : entree.type === "lien" ? (
          <>
            <span>{entree.nom}</span> <span className="raison">lien hors du clone</span>
          </>
        ) : (
          <button
            type="button"
            className={entree.type}
            onClick={() => (entree.type === "dossier" ? basculer(complet) : ouvrir(complet, entree.statut))}
          >
            {entree.nom}
          </button>
        )}
        {entree.statut && <Marqueur statut={entree.statut} dossier={entree.type === "dossier"} />}
        {deplie && (
          <ul role="group">
            <Entrees chemin={complet} dossiers={dossiers} deplies={deplies} basculer={basculer} ouvrir={ouvrir} />
          </ul>
        )}
      </li>
    );
  });
}

/** Lettre d’un fichier changé ; point d’un dossier qui contient des changements. */
function Marqueur({ statut, dossier }: { statut: StatutGit; dossier: boolean }) {
  const [lettre, libelle] = dossier ? ["●", "Contient des changements"] : MARQUEURS[statut];
  return (
    <span className="marqueur" title={libelle}>
      {lettre}
    </span>
  );
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

/** Les deux versions à montrer dans l’éditeur de diff, si le diff est lu et affichable ; côté HEAD
 * vide pour un fichier absent de HEAD. */
function versions(diff: Diff | undefined): { chemin: string; head: string; courant: string } | null {
  if (diff === undefined || "erreur" in diff || diff.courant === null) return null;
  return { chemin: diff.chemin, head: diff.head ?? "", courant: diff.courant };
}

/** Ce qui remplace l’éditeur de diff : lecture en cours, refus, ou « non affiché ». */
function EtatDiff({ diff }: { diff: Diff | undefined }) {
  if (diff === undefined) return <p className="etat-terminal">Lecture du diff…</p>;
  if ("erreur" in diff) return <p className="erreur">{diff.erreur}</p>;
  if (diff.courant === null)
    return (
      <p className="etat-terminal">
        {`${diff.non_affiche === "trop_gros" ? "Fichier de plus de 1 Mo" : "Fichier binaire"} : diff non affiché`}
      </p>
    );
  return null;
}

/** Éditeur de diff Monaco en lecture seule, HEAD à gauche et version courante à droite. */
function EditeurDiff({ diff }: { diff: { chemin: string; head: string; courant: string } | null }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const editeur = useRef<monaco.editor.IStandaloneDiffEditor | null>(null);

  useEffect(() => {
    editeur.current = monaco.editor.createDiffEditor(conteneur.current!, {
      readOnly: true,
      originalEditable: false,
      renderSideBySide: true,
      automaticLayout: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
    });
    return () => {
      editeur.current?.dispose();
      editeur.current = null;
    };
  }, []);

  const chemin = diff?.chemin;
  const head = diff?.head;
  const courant = diff?.courant;
  useEffect(() => {
    if (chemin === undefined || head === undefined || courant === undefined) {
      editeur.current?.setModel(null);
      return;
    }
    // Schémas propres au diff : pas de conflit avec le modèle `file:` de l’éditeur de fichier.
    const original = monaco.editor.createModel(
      head,
      undefined,
      monaco.Uri.from({ scheme: "head", path: `/${chemin}` }),
    );
    const modified = monaco.editor.createModel(
      courant,
      undefined,
      monaco.Uri.from({ scheme: "courant", path: `/${chemin}` }),
    );
    editeur.current?.setModel({ original, modified });
    return () => {
      // Monaco refuse qu’un modèle soit libéré avant d’être détaché de l’éditeur de diff.
      editeur.current?.setModel(null);
      original.dispose();
      modified.dispose();
    };
  }, [chemin, head, courant]);

  return <div className="editeur" ref={conteneur} hidden={diff === null} />;
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

/** La racine et les dossiers dépliés dont tous les parents le sont : ceux que l’arbre montre. */
function dossiersVisibles(deplies: ReadonlySet<string>): string[] {
  const visible = (chemin: string) => {
    const parties = chemin.split("/");
    return parties.every((_, i) => deplies.has(parties.slice(0, i + 1).join("/")));
  };
  return ["", ...[...deplies].filter(visible).sort((a, b) => a.localeCompare(b))];
}

/** `dossier` est `chemin` ou l’un de ses sous-dossiers. */
function contient(chemin: string, dossier: string): boolean {
  return dossier === chemin || dossier.startsWith(`${chemin}/`);
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
