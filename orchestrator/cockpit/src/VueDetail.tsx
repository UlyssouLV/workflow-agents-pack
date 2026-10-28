import {
  BugIcon,
  CheckIcon,
  ExternalLinkIcon,
  GitPullRequestIcon,
  HandIcon,
  PlayIcon,
  TriangleAlertIcon,
} from "lucide-react";
import { useEffect, useId, useState, type ReactNode } from "react";
import { toast } from "sonner";
import type {
  Agent,
  Bug,
  ChoixClone,
  CloneSale,
  Detail,
  Enfant,
  EtatCi,
  LienSession,
  ModeleCursor,
  Session,
  SessionsDuRepo,
  Version,
} from "./api";
import { ErreurApi, ID_SESSION, enregistrerPilote, lancerSession, lire } from "./api";
import { Alert, AlertDescription } from "./components/ui/alert";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "./components/ui/alert-dialog";
import { Badge, Pastille } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Label } from "./components/ui/label";
import { NativeSelect, NativeSelectOption } from "./components/ui/native-select";
import { Switch } from "./components/ui/switch";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/table";
import {
  BadgeSession,
  LIBELLES_ETAT_SESSION,
  LibelleEtape,
  LiensChaine,
  dateHeure,
  heure,
  libelleModele,
} from "./commun";
import { ContenuPage, Coque, EnTetePage } from "./Coque";
import { cn } from "./lib/utils";
import { RAFRAICHISSEMENT_SESSION_MS, useRafraichi } from "./rafraichi";

const LIBELLES_CI: Record<EtatCi, string> = {
  echec: "en échec",
  en_cours: "en cours",
  ok: "ok",
  aucune: "aucun check",
};

const VARIANTES_CI: Record<EtatCi, "echec" | "agent" | "succes" | "neutre"> = {
  echec: "echec",
  en_cours: "agent",
  ok: "succes",
  aucune: "neutre",
};

const RAISON_SESSION_OUVERTE = "session déjà ouverte sur ce repo";

/** `/repos/<owner>/<name>` : tout l’état du repo, relu en direct à chaque rafraîchissement. */
export function VueDetail({ owner, name }: { owner: string; name: string }) {
  const chemin = `/api/repos/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`;
  const { donnees, erreur } = useRafraichi<Detail>(chemin);
  const toutes = useRafraichi<SessionsDuRepo>("/api/sessions", RAFRAICHISSEMENT_SESSION_MS);

  return (
    <Coque courant="repos">
      <EnTetePage
        ariane={
          <>
            <a href="/">Repos</a> / {owner}
          </>
        }
        titre={
          donnees?.nom ?? (
            <>
              <span className="text-muted-foreground">{owner}/</span>
              {name}
            </>
          )
        }
        actions={
          donnees && (
            <Button variant="outline" size="sm" asChild>
              <a href={donnees.url} target="_blank" rel="noopener noreferrer" className="no-underline hover:no-underline">
                GitHub
                <ExternalLinkIcon aria-hidden />
              </a>
            </Button>
          )
        }
      />
      <ContenuPage>
        {erreur && <Erreur>{erreur}</Erreur>}
        {donnees && <Contenu detail={donnees} sessions={toutes.donnees?.sessions ?? []} />}
        <Sessions chemin={`${chemin}/sessions`} agents={donnees?.agents ?? []} />
      </ContenuPage>
    </Coque>
  );
}

function Erreur({ children }: { children: ReactNode }) {
  return (
    <Alert variant="destructive">
      <TriangleAlertIcon aria-hidden />
      <AlertDescription className="text-foreground">
        <p>{children}</p>
      </AlertDescription>
    </Alert>
  );
}

/** Sessions du repo, lues dans `jobs/` sans GitHub : affichées même quand le repo est en erreur. */
function Sessions({ chemin, agents }: { chemin: string; agents: Agent[] }) {
  const { donnees, erreur } = useRafraichi<SessionsDuRepo>(chemin, RAFRAICHISSEMENT_SESSION_MS);
  const nom = (id: Agent["id"]) => agents.find((a) => a.id === id)?.nom ?? id;
  const avecModele = (donnees?.sessions ?? []).some((s) => s.agent === "cursor");

  return (
    <Card role="region" aria-label="Sessions">
      <CardHeader>
        <CardTitle>
          <h2>Sessions</h2>
        </CardTitle>
      </CardHeader>
      {erreur && (
        <CardContent>
          <Erreur>{erreur}</Erreur>
        </CardContent>
      )}
      {donnees &&
        (donnees.sessions.length === 0 ? (
          <CardContent>
            <p className="text-muted-foreground">Aucune session.</p>
          </CardContent>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Date</TableHead>
                <TableHead>Agent</TableHead>
                {avecModele && <TableHead>Modèle</TableHead>}
                <TableHead>Commande</TableHead>
                <TableHead>État</TableHead>
                <TableHead>Chaîne</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {donnees.sessions.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="whitespace-nowrap tabular-nums">
                    <a href={s.url}>{dateHeure(s.debut)}</a>
                  </TableCell>
                  <TableCell>{nom(s.agent)}</TableCell>
                  {avecModele && <TableCell>{libelleModele(s)}</TableCell>}
                  <TableCell className="[overflow-wrap:anywhere]">
                    <code>{s.commande}</code>
                  </TableCell>
                  <TableCell>{LIBELLES_ETAT_SESSION[s.etat]}</TableCell>
                  <TableCell>
                    <LiensChaine session={s} libelles={["précédente", "suivante"]} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        ))}
    </Card>
  );
}

function Contenu({ detail, sessions }: { detail: Detail; sessions: Session[] }) {
  const [refus, setRefus] = useState<{ message: string; session: LienSession | null } | null>(null);

  if (detail.erreur) {
    return (
      <>
        <Erreur>{detail.erreur}</Erreur>
        <CarteRepo detail={detail} />
      </>
    );
  }

  return (
    <>
      {detail.humain_requis && (
        <Alert variant="attention" role="status">
          <HandIcon aria-hidden />
          <AlertDescription className="text-foreground">
            <p>
              <strong>Intervention humaine requise.</strong> Étape : {detail.etape?.libelle}.
            </p>
          </AlertDescription>
        </Alert>
      )}
      {refus && (
        <Erreur>
          Lancement refusé : {refus.message}
          {refus.session && (
            <>
              {" "}
              — <a href={refus.session.url}>voir la session ouverte</a>
            </>
          )}
        </Erreur>
      )}
      <GrilleDetail
        droite={
          <>
            <LancerSession detail={detail} sessions={sessions} refuser={setRefus} />
            <CarteRepo detail={detail} />
          </>
        }
      >
        {detail.versions.map((v) => (
          <CarteVersion key={v.numero} version={v} />
        ))}
        <Bugs bugs={detail.bugs} />
      </GrilleDetail>
    </>
  );
}

/** Deux colonnes sur grand écran (contenu, puis lancement et repo) ; une seule sur téléphone. */
function GrilleDetail({ children, droite }: { children: ReactNode; droite: ReactNode }) {
  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="grid min-w-0 gap-5">{children}</div>
      <div className="grid min-w-0 gap-5">{droite}</div>
    </div>
  );
}

function LancerSession({
  detail,
  sessions,
  refuser,
}: {
  detail: Detail;
  sessions: Session[];
  refuser: (refus: { message: string; session: LienSession | null } | null) => void;
}) {
  const [pilote, setPilote] = useState(detail.pilote);
  const [agent, setAgent] = useState<Agent["id"]>(detail.agent);
  const [modelePref, setModelePref] = useState<string | null>(detail.modele);
  const [modeleLancement, setModeleLancement] = useState<string | null>(detail.modele);
  const [branche, setBranche] = useState(() => detail.branches.defaut);
  // Clone sale au lancement : rien n’est lancé tant que l’utilisateur n’a pas choisi.
  const [sale, setSale] = useState<CloneSale | null>(null);
  const [modeles, setModeles] = useState<ModeleCursor[] | null>(null);
  const [erreurModeles, setErreurModeles] = useState<string | null>(null);
  const cursorConnecte = Boolean(detail.agents.find((a) => a.id === "cursor")?.connecte);
  const ids = { pilote: useId(), aide: useId(), agent: useId(), modele: useId(), branche: useId(), session: useId() };

  useEffect(() => {
    setPilote(detail.pilote);
    setAgent(detail.agent);
    setModelePref(detail.modele);
  }, [detail.pilote, detail.agent, detail.modele]);

  useEffect(() => {
    if (!cursorConnecte) {
      setModeles(null);
      setErreurModeles(null);
      return;
    }
    lire<{ modeles: ModeleCursor[] }>("/api/modeles").then(
      (donnees) => {
        setModeles(donnees.modeles);
        setErreurModeles(null);
      },
      (erreur: Error) => {
        setModeles(null);
        setErreurModeles(erreur.message);
      },
    );
  }, [cursorConnecte]);

  const persister = (suivant: { pilote: boolean; agent: Agent["id"]; modele?: string | null }) => {
    setPilote(suivant.pilote);
    setAgent(suivant.agent);
    if (suivant.modele !== undefined) {
      setModelePref(suivant.modele);
      setModeleLancement(suivant.modele);
    }
    enregistrerPilote(detail.slug, suivant.pilote, suivant.agent, suivant.modele).then(
      () => toast.success("Préférence enregistrée"),
      (erreur: Error) => {
        refuser({
          message: erreur.message,
          session: erreur instanceof ErreurApi ? erreur.session : null,
        });
      },
    );
  };

  const choisi = detail.agents.find((a) => a.id === agent);
  const montreModele = agent === "cursor" && cursorConnecte;
  const travaille = sessions.find(
    (s) =>
      s.etat === "ouverte" &&
      s.activite === "travaille" &&
      s.repo.toLowerCase() !== detail.slug.toLowerCase(),
  );
  const raison = !choisi?.connecte
    ? "agent non connecté"
    : montreModele && erreurModeles
      ? erreurModeles
      : montreModele && !modeles
        ? "liste des modèles Cursor indisponible"
        : detail.session
          ? RAISON_SESSION_OUVERTE
          : travaille
            ? `une session travaille sur ${travaille.repo}`
            : null;
  const ouverte =
    detail.session && raison === RAISON_SESSION_OUVERTE
      ? detail.session
      : travaille && raison?.startsWith("une session travaille")
        ? travaille
        : null;

  const lancer = (choix?: ChoixClone) => {
    refuser(null);
    setSale(null);
    lancerSession(
      detail.slug,
      agent,
      branche,
      choix,
      agent === "cursor" ? modeleLancement : undefined,
    ).then(
      (session) => {
        // Page bâtie ici, pas l’URL de la réponse : on ne quitte pas le cockpit.
        if (ID_SESSION.test(session.id)) window.location.assign(`/sessions/${session.id}`);
      },
      (erreur: Error) => {
        if (erreur instanceof ErreurApi && erreur.clone) {
          setSale(erreur.clone);
        } else {
          refuser({ message: erreur.message, session: erreur instanceof ErreurApi ? erreur.session : null });
        }
      },
    );
  };

  return (
    <Card role="region" aria-label="Lancer une session">
      <CardHeader>
        <CardTitle>
          <h2>Lancer une session</h2>
        </CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3.5">
        <div className="flex items-center justify-between gap-3 rounded-md border bg-surface-2 px-3.5 py-3">
          <div>
            <strong id={ids.pilote}>Pilote</strong>
            <p id={ids.aide} className="mt-0.5 text-xs text-muted-foreground">
              Lance seul le premier /implement éligible et reprend après chaque arrêt.
            </p>
          </div>
          <Switch
            aria-labelledby={ids.pilote}
            aria-describedby={ids.aide}
            checked={pilote}
            onCheckedChange={(coche) => persister({ pilote: coche, agent })}
          />
        </div>
        {detail.session && (
          <p className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
            <BadgeSession session={detail.session} /> sur {detail.session.repo}
          </p>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <Champ id={ids.agent} libelle="Agent">
            <NativeSelect
              id={ids.agent}
              value={agent}
              onChange={(e) => persister({ pilote, agent: e.target.value as Agent["id"] })}
            >
              {detail.agents.map((a) => (
                <NativeSelectOption key={a.id} value={a.id}>
                  {a.nom}
                  {!a.connecte && " (non connecté)"}
                </NativeSelectOption>
              ))}
            </NativeSelect>
          </Champ>
          {montreModele && modeles && (
            <SelectModele
              id={ids.modele}
              libelle="Modèle préféré"
              value={modelePref}
              modeles={modeles}
              onChange={(modele) => persister({ pilote, agent, modele })}
            />
          )}
        </div>
        <div className="h-px bg-border" />
        <Champ id={ids.branche} libelle="Branche">
          <NativeSelect id={ids.branche} value={branche} onChange={(e) => setBranche(e.target.value)}>
            {detail.branches.proposees.map((b) => (
              <NativeSelectOption key={b} value={b}>
                {b}
              </NativeSelectOption>
            ))}
          </NativeSelect>
        </Champ>
        {montreModele && modeles && (
          <SelectModele
            id={ids.session}
            libelle="Modèle de la session"
            value={modeleLancement}
            modeles={modeles}
            onChange={setModeleLancement}
          />
        )}
        <Button type="button" disabled={raison !== null} title={raison ?? undefined} onClick={() => lancer()}>
          <PlayIcon aria-hidden />
          Nouvelle session
        </Button>
        {raison && (
          <p className="flex items-start gap-1.5 text-[12.5px] text-muted-foreground [&>svg]:mt-0.5 [&>svg]:size-3.5 [&>svg]:shrink-0">
            <TriangleAlertIcon aria-hidden />
            <span>
              {raison}
              {ouverte && (
                <>
                  {" "}
                  — <a href={ouverte.url} className="text-agent">voir la session ouverte</a>
                </>
              )}
            </span>
          </p>
        )}
      </CardContent>
      <ChoixCloneSale clone={sale} choisir={lancer} annuler={() => setSale(null)} />
    </Card>
  );
}

function Champ({ id, libelle, children }: { id: string; libelle: string; children: ReactNode }) {
  return (
    <div className="grid min-w-0 gap-1.5">
      <Label htmlFor={id}>{libelle}</Label>
      {children}
    </div>
  );
}

function SelectModele({
  id,
  libelle,
  value,
  modeles,
  onChange,
}: {
  id: string;
  libelle: string;
  value: string | null;
  modeles: ModeleCursor[];
  onChange: (modele: string | null) => void;
}) {
  return (
    <Champ id={id} libelle={libelle}>
      <NativeSelect
        id={id}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
      >
        {modeles.map((m) => (
          <NativeSelectOption key={m.id ?? "auto"} value={m.id ?? ""}>
            {m.libelle}
          </NativeSelectOption>
        ))}
      </NativeSelect>
    </Champ>
  );
}

function CarteRepo({ detail }: { detail: Detail }) {
  return (
    <Card role="region" aria-label="Repo">
      <CardContent>
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2 text-[13px] [&_dd]:[overflow-wrap:anywhere] [&_dt]:text-muted-foreground">
          <dt>Repo</dt>
          <dd>
            <a href={detail.url}>{detail.url.replace("https://", "")}</a>
          </dd>
          {detail.etape && (
            <>
              <dt>Étape</dt>
              <dd>{detail.etape.libelle}</dd>
            </>
          )}
          <dt>Lu à</dt>
          <dd className="tabular-nums">{heure(detail.lu_a)}</dd>
        </dl>
      </CardContent>
    </Card>
  );
}

function Numero({ children }: { children: ReactNode }) {
  return (
    <>
      <span className="font-mono text-[12.5px] text-muted-foreground">{children}</span>{" "}
    </>
  );
}

function CarteVersion({ version }: { version: Version }) {
  const nom = `#${version.numero} ${version.titre}`;
  const { completed, total } = version.progression;
  return (
    <Card role="region" aria-label={nom}>
      <CardHeader>
        <CardTitle className="min-w-0 flex-1">
          <h2>
            <a href={version.url} className="no-underline hover:underline">
              <Numero>#{version.numero}</Numero>
              {version.titre}
            </a>
          </h2>
        </CardTitle>
        <div className="flex min-w-[160px] items-center gap-2.5">
          <div
            role="progressbar"
            aria-label={`Progression #${version.numero}`}
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={completed}
            className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-3"
          >
            <div
              className="h-full rounded-[inherit] bg-foreground"
              style={{ width: `${total > 0 ? (completed / total) * 100 : 0}%` }}
            />
          </div>
          <span className="text-[12.5px] text-muted-foreground tabular-nums">
            {completed}/{total}
          </span>
        </div>
      </CardHeader>
      <CardContent className="grid gap-2 text-muted-foreground">
        <p>
          Étape : <LibelleEtape etape={version.etape} />
        </p>
        {version.signaux.length > 0 && (
          <ul aria-label="Signaux" className="flex flex-wrap gap-1.5">
            {version.signaux.map((s) => (
              <li key={s.numero}>
                <Badge variant={s.humain ? "attention" : "neutre"}>
                  {s.humain && <HandIcon aria-hidden />}
                  {s.libelle}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
      <Table aria-label="Enfants">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>Enfant</TableHead>
            <TableHead>État</TableHead>
            <TableHead>Labels</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {version.enfants.map((e) => (
            <TableRow key={e.numero}>
              <TableCell className="min-w-[12rem] whitespace-normal">
                <a href={e.url} className="no-underline hover:underline">
                  <Numero>#{e.numero}</Numero>
                  {e.titre}
                </a>
              </TableCell>
              <TableCell>
                <EtatEnfant enfant={e} />
              </TableCell>
              <TableCell>
                {e.labels.length > 0 ? (
                  <span className="flex flex-wrap gap-1">
                    {e.labels.map((l) => (
                      <Puce key={l}>{l}</Puce>
                    ))}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <PrVersion version={version} />
    </Card>
  );
}

function EtatEnfant({ enfant }: { enfant: Enfant }) {
  return (
    <span className="flex flex-wrap gap-1">
      {enfant.ouvert ? (
        <Badge variant="attention">Ouvert</Badge>
      ) : (
        <Badge variant="succes">
          <CheckIcon aria-hidden />
          Fermé
        </Badge>
      )}
      {enfant.bloque && <Badge variant="neutre">Bloqué</Badge>}
    </span>
  );
}

function Puce({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block rounded-sm bg-surface-3 px-1.5 py-px font-mono text-[11.5px] text-muted-foreground">
      {children}
    </span>
  );
}

function PrVersion({ version }: { version: Version }) {
  const { pr } = version;
  const pied = "grid gap-3 rounded-b-lg border-t bg-surface-2 px-4.5 py-3.5";
  if (pr === null) {
    return (
      <div className={cn(pied, "text-muted-foreground")}>
        <p>Aucune PR de version (corps contenant « Fixes #{version.numero} »).</p>
      </div>
    );
  }
  return (
    <div className={pied}>
      <p className="flex flex-wrap items-center gap-2 font-medium [&>svg]:size-4 [&>svg]:text-muted-foreground">
        <GitPullRequestIcon aria-hidden />
        <a href={pr.url} className="no-underline hover:underline">
          <Numero>PR #{pr.numero}</Numero>
          {pr.titre}
        </a>
        {pr.brouillon && <Badge variant="neutre">Brouillon</Badge>}
        <Badge variant={VARIANTES_CI[pr.ci]}>
          {pr.ci === "en_cours" && <Pastille vivant />}
          CI {LIBELLES_CI[pr.ci]}
        </Badge>
      </p>
      {pr.checks.length > 0 && (
        <ul aria-label="Checks" className="grid gap-1.5 text-[13px]">
          {pr.checks.map((c) => (
            <li key={c.nom} aria-label={c.nom} className="flex items-center gap-2.5">
              <Badge variant={VARIANTES_CI[c.etat]}>
                {c.etat === "ok" && <CheckIcon aria-hidden />}
                {LIBELLES_CI[c.etat]}
              </Badge>
              {c.url ? (
                <a href={c.url} className="no-underline hover:underline">
                  {c.nom}
                </a>
              ) : (
                c.nom
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Clone sale : les changements laissés par une session précédente, à reprendre ou jeter (Échap = Annuler). */
function ChoixCloneSale({
  clone,
  choisir,
  annuler,
}: {
  clone: CloneSale | null;
  choisir: (choix: ChoixClone) => void;
  annuler: () => void;
}) {
  const n = clone?.fichiers.length ?? 0;
  return (
    <AlertDialog open={clone !== null} onOpenChange={(ouvert) => !ouvert && annuler()}>
      <AlertDialogContent className="max-w-2xl">
        {clone && (
          <>
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2.5 [&>svg]:size-5 [&>svg]:text-attention">
                <TriangleAlertIcon aria-hidden />
                Le clone a des changements non commités
              </AlertDialogTitle>
              <AlertDialogDescription className="[&_strong]:text-foreground">
                Une session précédente les a laissés sur <code className="text-foreground">{clone.branche}</code> ({n}{" "}
                fichier{n > 1 ? "s" : ""} modifié{n > 1 ? "s" : ""}). <strong>Reprendre</strong> lance sur cette
                branche, sans la changer ; <strong>Jeter</strong> les garde dans <code>abandon.patch</code> de la
                session, remet le clone à zéro puis passe sur la branche choisie.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <ul aria-label="Fichiers modifiés" className="grid gap-1 font-mono text-[12.5px]">
              {clone.fichiers.map((f) => (
                <li key={f.chemin} className="[overflow-wrap:anywhere]">
                  <span className={f.statut === "??" ? "text-succes" : "text-attention"}>{f.statut}</span> {f.chemin}
                </li>
              ))}
            </ul>
            <pre
              aria-label="Diff"
              className="max-h-[200px] overflow-auto rounded-md border bg-terminal p-3 font-mono text-xs leading-relaxed"
            >
              {clone.diff}
            </pre>
            <AlertDialogFooter>
              <AlertDialogCancel>Annuler</AlertDialogCancel>
              <Button variant="destructive" onClick={() => choisir("jeter")}>
                Jeter
              </Button>
              <Button onClick={() => choisir("reprendre")}>Reprendre</Button>
            </AlertDialogFooter>
          </>
        )}
      </AlertDialogContent>
    </AlertDialog>
  );
}

function Bugs({ bugs }: { bugs: Bug[] }) {
  return (
    <Card role="region" aria-label="Bugs ouverts">
      <CardHeader className="[&>svg]:size-4 [&>svg]:text-muted-foreground">
        <BugIcon aria-hidden />
        <CardTitle>
          <h2>Bugs ouverts</h2>
        </CardTitle>
        <span className="text-xs text-muted-foreground tabular-nums">{bugs.length}</span>
      </CardHeader>
      {bugs.length === 0 ? (
        <CardContent>
          <p className="text-muted-foreground">Aucun.</p>
        </CardContent>
      ) : (
        <ul className="grid divide-y">
          {bugs.map((b) => (
            <li key={b.numero} className="px-4.5 py-2.5">
              <a href={b.url} className="no-underline hover:underline">
                <Numero>#{b.numero}</Numero>
                {b.titre}
              </a>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
