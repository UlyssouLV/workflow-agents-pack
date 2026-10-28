import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { HandIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { urlTerminal } from "./api";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { optionsXterm, remesurerApresPolice } from "./themeXterm";

/** Délai avant de se reconnecter à un terminal fermé alors que la page le montre encore. */
export const RECONNEXION_MS = 2_000;

type Etat = "connexion" | "ecriture" | "lecture" | "ferme";

const MESSAGES: Record<Etat, string> = {
  connexion: "Connexion au terminal…",
  ecriture: "Ce que vous tapez part à l’agent.",
  lecture: "Un autre onglet a la main.",
  ferme: "Terminal déconnecté.",
};

/** Terminal de l’agent (xterm.js), relié par websocket au runtime qui relaie jusqu’à tmux.
 *
 * Le runtime annonce le rôle (`{"role": "ecriture"|"lecture"}`) puis envoie la sortie en
 * binaire ; seul l’onglet qui a la main envoie sa saisie et sa taille. Un onglet en lecture
 * seule peut la prendre (`{"prendre": true}`) ; le runtime lui annonce alors l’écriture.
 *
 * Quitter la page ferme le websocket, pas la session, et libère la main. Les liens rechargent
 * le document sans démonter le composant, et le navigateur peut garder la page en mémoire
 * (cache de l’historique) avec son websocket ouvert : il est donc fermé dès `pagehide`, et
 * rouvert si la page revient de ce cache.
 *
 * Fermé par le runtime alors que la page le garde (session encore ouverte), il se reconnecte : la
 * suivante d’une chaîne est ouverte avant que son tmux tourne. Une session finie le remplace par
 * sa relecture à la lecture suivante de la page.
 *
 * `reprendre` : l’onglet avait la main sur la session précédente de la chaîne ; annoncé en lecture
 * avant de l’avoir eue ici, il la prend. `surRole` reçoit chaque rôle annoncé. */
export function TerminalEnDirect({
  id,
  reprendre = false,
  surRole,
}: {
  id: string;
  reprendre?: boolean;
  surRole?: (ecriture: boolean) => void;
}) {
  const conteneur = useRef<HTMLDivElement>(null);
  const prendre = useRef<() => void>(() => {});
  const [etat, setEtat] = useState<Etat>("connexion");
  const [connexion, setConnexion] = useState(0);
  const aReprendre = useRef(reprendre);
  const rappelRole = useRef(surRole);
  rappelRole.current = surRole;

  useEffect(() => {
    const revenir = (evenement: PageTransitionEvent) => {
      if (evenement.persisted) setConnexion((n) => n + 1);
    };
    window.addEventListener("pageshow", revenir);
    return () => window.removeEventListener("pageshow", revenir);
  }, []);

  useEffect(() => {
    setEtat("connexion");
    const terminal = new Terminal({ ...optionsXterm(), disableStdin: true });
    const ajustement = new FitAddon();
    terminal.loadAddon(ajustement);
    terminal.open(conteneur.current!);
    let actif = true;
    remesurerApresPolice(terminal, () => actif);
    const ws = new WebSocket(urlTerminal(id));
    ws.binaryType = "arraybuffer";
    let ecriture = false;

    const envoyer = (message: object) => {
      if (ecriture && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(message));
    };
    prendre.current = () => {
      if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ prendre: true }));
    };
    const ajuster = () => {
      ajustement.fit();
      envoyer({ taille: { colonnes: terminal.cols, lignes: terminal.rows } });
    };

    ws.onmessage = (evenement: MessageEvent) => {
      if (typeof evenement.data !== "string") {
        terminal.write(new Uint8Array(evenement.data as ArrayBuffer));
        return;
      }
      ecriture = JSON.parse(evenement.data).role === "ecriture";
      rappelRole.current?.(ecriture);
      // Due jusqu’à ce que l’onglet l’ait : une connexion coupée avant ne la consomme pas.
      if (ecriture) aReprendre.current = false;
      else if (aReprendre.current) prendre.current();
      terminal.options.disableStdin = !ecriture;
      setEtat(ecriture ? "ecriture" : "lecture");
      ajuster();
      if (ecriture) terminal.focus();
    };
    let reconnexion: ReturnType<typeof setTimeout> | undefined;
    ws.onclose = () => {
      ecriture = false;
      terminal.options.disableStdin = true;
      setEtat("ferme");
      reconnexion = setTimeout(() => setConnexion((n) => n + 1), RECONNEXION_MS);
    };
    const saisie = terminal.onData((donnees) => envoyer({ saisie: donnees }));
    const quitter = () => {
      ws.onclose = null;
      ws.close();
    };
    ajuster();
    window.addEventListener("resize", ajuster);
    window.addEventListener("pagehide", quitter);

    return () => {
      actif = false;
      window.removeEventListener("resize", ajuster);
      window.removeEventListener("pagehide", quitter);
      saisie.dispose();
      clearTimeout(reconnexion);
      quitter();
      terminal.dispose();
    };
  }, [id, connexion]);

  return (
    <section aria-label="Terminal" className="overflow-hidden rounded-lg border bg-terminal">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-card px-3 py-2 text-[12.5px]">
        {etat === "ecriture" && (
          <Badge variant="succes">
            <HandIcon aria-hidden />
            Vous avez la main
          </Badge>
        )}
        {etat === "lecture" && <Badge variant="neutre">Lecture seule</Badge>}
        <span className="text-muted-foreground">{MESSAGES[etat]}</span>
        {etat === "lecture" && (
          <Button variant="outline" size="sm" className="ml-auto" onClick={() => prendre.current()}>
            <HandIcon aria-hidden />
            Prendre la main
          </Button>
        )}
      </div>
      <div className="h-[min(58vh,520px)] p-2" ref={conteneur} />
    </section>
  );
}
