import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { urlTerminal } from "./api";

type Etat = "connexion" | "ecriture" | "lecture" | "ferme";

const MESSAGES: Record<Etat, string | null> = {
  connexion: "Connexion au terminal…",
  ecriture: null,
  lecture: "Lecture seule : un autre onglet a la main.",
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
 * rouvert si la page revient de ce cache. */
export function TerminalEnDirect({ id }: { id: string }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const prendre = useRef<() => void>(() => {});
  const [etat, setEtat] = useState<Etat>("connexion");
  const [connexion, setConnexion] = useState(0);

  useEffect(() => {
    const revenir = (evenement: PageTransitionEvent) => {
      if (evenement.persisted) setConnexion((n) => n + 1);
    };
    window.addEventListener("pageshow", revenir);
    return () => window.removeEventListener("pageshow", revenir);
  }, []);

  useEffect(() => {
    setEtat("connexion");
    const terminal = new Terminal({ cursorBlink: true, disableStdin: true });
    const ajustement = new FitAddon();
    terminal.loadAddon(ajustement);
    terminal.open(conteneur.current!);
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
      terminal.options.disableStdin = !ecriture;
      setEtat(ecriture ? "ecriture" : "lecture");
      ajuster();
      if (ecriture) terminal.focus();
    };
    ws.onclose = () => {
      ecriture = false;
      terminal.options.disableStdin = true;
      setEtat("ferme");
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
      window.removeEventListener("resize", ajuster);
      window.removeEventListener("pagehide", quitter);
      saisie.dispose();
      quitter();
      terminal.dispose();
    };
  }, [id, connexion]);

  const message = MESSAGES[etat];
  return (
    <section aria-label="Terminal">
      {message && (
        <p className="etat-terminal">
          {message}
          {etat === "lecture" && (
            <>
              {" "}
              <button type="button" onClick={() => prendre.current()}>
                Prendre la main
              </button>
            </>
          )}
        </p>
      )}
      <div className="terminal" ref={conteneur} />
    </section>
  );
}
