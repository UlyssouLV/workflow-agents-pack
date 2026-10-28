import {
  CameraIcon,
  CameraOffIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  DiffIcon,
  FileIcon,
  FolderIcon,
  FolderOpenIcon,
  GitBranchIcon,
  XIcon,
} from "lucide-react";
import { type CSSProperties, useEffect, useRef, useState } from "react";
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
import { dateHeure, Erreur } from "./commun";
import { Alert, AlertDescription } from "./components/ui/alert";
import { Badge, Pastille } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { cn } from "./lib/utils";
import { monaco } from "./monaco";
import { optionsMonaco, remesurerApresPolice, THEME_MONACO, themeMonaco } from "./themeMonaco";

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

/** Couleur d’une entrée changée, comme son marqueur. */
const COULEURS_STATUT: Record<StatutGit, string> = {
  modifie: "text-git-modifie",
  ajoute: "text-git-ajoute",
  non_suivi: "text-git-ajoute",
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

  const ouvrir = (chemin: string) => {
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
      // Son statut Git (le bouton de diff) vient de son dossier, même replié depuis.
      const parent = parentDe(courant.fichier);
      if (!courant.dossiers.includes(parent)) charger(parent);
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
  // Relu avec son dossier : un fichier changé depuis son ouverture a son diff.
  const statutActif = actif === null ? null : statutDe(dossiers, actif);
  const instantane = identite !== null && !("erreur" in identite) && identite.source === "instantane" ? identite.instantane : null;

  return (
    <div className="grid min-w-0 gap-3">
      {instantane?.etat === "present" && (
        <Alert variant="agent" role="status">
          <CameraIcon aria-hidden />
          <AlertDescription className="text-foreground">
            <p>
              <strong>Instantané de fin de session</strong> — {dateHeure(instantane.pris_le)}. Les fichiers ignorés
              n’ont pas été conservés.
            </p>
          </AlertDescription>
        </Alert>
      )}
      <EnteteCodespace identite={identite} enDirect={enDirect} />
      {instantane && instantane.etat !== "present" ? (
        <Alert role="status">
          <CameraOffIcon aria-hidden />
          <AlertDescription>
            <p>{sansInstantane(instantane)}</p>
          </AlertDescription>
        </Alert>
      ) : (
        // Sur téléphone, l’arbre au-dessus de l’éditeur.
        <div className="grid min-h-[520px] grid-rows-[180px_minmax(0,1fr)] overflow-hidden rounded-lg border bg-terminal min-[900px]:h-[min(62vh,560px)] min-[900px]:min-h-0 min-[900px]:grid-cols-[260px_minmax(0,1fr)] min-[900px]:grid-rows-1">
          <ul
            role="tree"
            aria-label="Fichiers du codespace"
            className="overflow-auto border-b bg-card py-2 font-mono text-[12.5px] min-[900px]:border-r min-[900px]:border-b-0"
          >
            <Entrees
              chemin=""
              profondeur={0}
              dossiers={dossiers}
              deplies={deplies}
              actif={actif}
              basculer={basculer}
              ouvrir={ouvrir}
            />
          </ul>
          <section aria-label="Fichier" className="flex min-h-0 min-w-0 flex-col">
            {ouverts.length > 0 && (
              <div className="flex items-stretch border-b bg-card">
                <div role="tablist" aria-label="Fichiers ouverts" className="flex min-w-0 flex-1 overflow-x-auto">
                  {ouverts.map((chemin) => (
                    <span
                      key={chemin}
                      className="flex h-[34px] shrink-0 items-center gap-1.5 border-t-2 border-r border-t-transparent pr-1.5 pl-3 font-mono text-[12.5px] text-muted-foreground has-[[aria-selected=true]]:border-t-attention has-[[aria-selected=true]]:bg-terminal has-[[aria-selected=true]]:text-foreground"
                    >
                      <button
                        type="button"
                        role="tab"
                        aria-selected={chemin === actif}
                        title={chemin}
                        onClick={() => activer(chemin)}
                        className="cursor-pointer"
                      >
                        {nomDe(chemin)}
                      </button>
                      <button
                        type="button"
                        aria-label={`Fermer ${nomDe(chemin)}`}
                        onClick={() => fermer(chemin)}
                        className="grid size-5.5 cursor-pointer place-items-center rounded-sm text-faint hover:bg-surface-3 hover:text-foreground"
                      >
                        <XIcon aria-hidden className="size-3.5" />
                      </button>
                    </span>
                  ))}
                </div>
                {actif !== null && (statutActif || diffActif) && (
                  <div className="flex items-center px-2">
                    <Button
                      variant={diffActif ? "secondary" : "ghost"}
                      size="sm"
                      aria-pressed={diffActif}
                      onClick={() => basculerDiff(actif)}
                    >
                      <DiffIcon aria-hidden />
                      Diff avec HEAD
                    </Button>
                  </div>
                )}
              </div>
            )}
            {actif === null && <p className="m-auto p-4 text-muted-foreground">Ouvrez un fichier dans l’arbre.</p>}
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

function EnteteCodespace({
  identite,
  enDirect,
}: {
  identite: IdentiteCodespace | { erreur: string } | null;
  enDirect: boolean;
}) {
  if (identite === null) return <p className="text-muted-foreground">Lecture du codespace…</p>;
  if ("erreur" in identite) return <Erreur>{identite.erreur}</Erreur>;
  const { repo, branche, head } = identite;
  return (
    <p
      role="group"
      aria-label="Identité du codespace"
      className="flex flex-wrap items-center gap-x-4.5 gap-y-2 text-[12.5px] text-muted-foreground [&_svg]:size-4"
    >
      <span className="inline-flex min-w-0 items-center gap-1.5 [overflow-wrap:anywhere]">
        <FolderIcon aria-hidden />
        <strong className="font-medium text-foreground">{repo}</strong>
      </span>
      <span className="inline-flex min-w-0 items-center gap-1.5 [overflow-wrap:anywhere]">
        <GitBranchIcon aria-hidden />
        {branche ? (
          <a
            href={`https://github.com/${repo}/tree/${branche.split("/").map(encodeURIComponent).join("/")}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-agent no-underline hover:underline"
          >
            {branche}
          </a>
        ) : (
          "HEAD détaché"
        )}
      </span>
      <span>
        HEAD {head ? <code className="font-medium text-foreground">{head}</code> : "aucun commit"}
      </span>
      {enDirect && (
        <Badge variant="agent">
          <Pastille vivant />
          En direct
        </Badge>
      )}
    </p>
  );
}

interface PropsEntrees {
  chemin: string;
  profondeur: number;
  dossiers: Record<string, Dossier>;
  deplies: ReadonlySet<string>;
  actif: string | null;
  basculer: (chemin: string) => void;
  ouvrir: (chemin: string) => void;
}

/** Ligne de l’arbre : toute la largeur, décalée selon la profondeur. */
const LIGNE = "flex items-center gap-1.5 py-0.75 pr-3 pl-[calc(0.75rem+var(--profondeur)*0.875rem)] whitespace-nowrap";

/** Les entrées du dossier `chemin`, une fois chargé ; un dossier déplié montre les siennes. */
function Entrees({ chemin, profondeur, dossiers, deplies, actif, basculer, ouvrir }: PropsEntrees) {
  const decalage = { "--profondeur": profondeur } as CSSProperties;
  const dossier = dossiers[chemin];
  if (dossier === undefined)
    return (
      <li className={cn(LIGNE, "text-muted-foreground")} style={decalage}>
        Chargement…
      </li>
    );
  if ("erreur" in dossier)
    return (
      <li role="alert" className={cn(LIGNE, "whitespace-normal text-echec")} style={decalage}>
        {dossier.erreur}
      </li>
    );
  return dossier.map((entree) => {
    const complet = chemin ? `${chemin}/${entree.nom}` : entree.nom;
    const estDossier = entree.type === "dossier";
    const deplie = deplies.has(complet);
    const Chevron = deplie ? ChevronDownIcon : ChevronRightIcon;
    const Icone = estDossier ? (deplie ? FolderOpenIcon : FolderIcon) : FileIcon;
    const nom = (
      <>
        {estDossier && !entree.non_conserve ? <Chevron aria-hidden /> : <span aria-hidden className="size-3.5 shrink-0" />}
        <Icone aria-hidden className="opacity-80" />
        <span className="truncate">{entree.nom}</span>
      </>
    );
    return (
      <li
        key={entree.nom}
        role="treeitem"
        aria-label={entree.nom}
        aria-expanded={estDossier ? deplie : undefined}
        aria-selected={estDossier ? undefined : complet === actif}
      >
        <div
          title={entree.ignore ? "Ignoré par Git" : undefined}
          className={cn(
            LIGNE,
            "hover:bg-surface-2 [&_svg]:size-3.5 [&_svg]:shrink-0",
            complet === actif && "bg-surface-3",
            entree.statut && COULEURS_STATUT[entree.statut],
            entree.ignore && "text-faint",
            entree.non_conserve && "text-faint italic",
          )}
          style={decalage}
        >
          {entree.non_conserve || entree.type === "lien" ? (
            <span className="flex min-w-0 items-center gap-1.5">
              {nom}
              <span className="text-[11px] text-faint italic">
                {entree.non_conserve ? "non conservé" : "lien hors du clone"}
              </span>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => (estDossier ? basculer(complet) : ouvrir(complet))}
              className="flex min-w-0 flex-1 cursor-pointer items-center gap-1.5 text-left"
            >
              {nom}
            </button>
          )}
          {entree.statut && <Marqueur statut={entree.statut} dossier={estDossier} />}
        </div>
        {deplie && (
          <ul role="group">
            <Entrees
              chemin={complet}
              profondeur={profondeur + 1}
              dossiers={dossiers}
              deplies={deplies}
              actif={actif}
              basculer={basculer}
              ouvrir={ouvrir}
            />
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
    <span className="ml-auto pl-2 text-[11px] font-semibold" title={libelle}>
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
  if (fichier === undefined) return <p className="p-4 text-muted-foreground">Lecture du fichier…</p>;
  if ("erreur" in fichier) return <p className="p-4 text-echec">{fichier.erreur}</p>;
  if (fichier.contenu === null)
    return (
      <p className="p-4 text-muted-foreground">
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
  if (diff === undefined) return <p className="p-4 text-muted-foreground">Lecture du diff…</p>;
  if ("erreur" in diff) return <p className="p-4 text-echec">{diff.erreur}</p>;
  if (diff.courant === null)
    return (
      <p className="p-4 text-muted-foreground">
        {`${diff.non_affiche === "trop_gros" ? "Fichier de plus de 1 Mo" : "Fichier binaire"} : diff non affiché`}
      </p>
    );
  return null;
}

/** Thème et police des éditeurs, tirés des variables de `:root` (index.css). */
function preparerMonaco() {
  monaco.editor.defineTheme(THEME_MONACO, themeMonaco());
  const options = optionsMonaco();
  remesurerApresPolice(options, () => monaco.editor.remeasureFonts());
  return options;
}

/** Éditeur de diff Monaco en lecture seule, HEAD à gauche et version courante à droite. */
function EditeurDiff({ diff }: { diff: { chemin: string; head: string; courant: string } | null }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const editeur = useRef<monaco.editor.IStandaloneDiffEditor | null>(null);

  useEffect(() => {
    editeur.current = monaco.editor.createDiffEditor(conteneur.current!, {
      ...preparerMonaco(),
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

  return <div className="min-h-0 flex-1" ref={conteneur} hidden={diff === null} />;
}

/** Monaco en lecture seule, caché sans fichier à montrer ; le langage (coloration) se déduit du
 * nom du fichier. */
function EditeurMonaco({ fichier }: { fichier: { chemin: string; contenu: string } | null }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const editeur = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    editeur.current = monaco.editor.create(conteneur.current!, {
      ...preparerMonaco(),
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

  return <div className="min-h-0 flex-1" ref={conteneur} hidden={fichier === null} />;
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

/** Le statut Git du fichier `chemin`, tel que son dossier chargé le montre. */
function statutDe(dossiers: Record<string, Dossier>, chemin: string): StatutGit | null {
  const dossier = dossiers[parentDe(chemin)];
  if (dossier === undefined || "erreur" in dossier) return null;
  return dossier.find((e) => e.nom === nomDe(chemin))?.statut ?? null;
}

function parentDe(chemin: string): string {
  return chemin.slice(0, Math.max(chemin.lastIndexOf("/"), 0));
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
