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
 * binaire ; seul l’onglet qui a la main envoie sa saisie et sa taille. Démonter le composant
 * ferme le websocket, pas la session. */
export function TerminalEnDirect({ id }: { id: string }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const [etat, setEtat] = useState<Etat>("connexion");

  useEffect(() => {
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
    ajuster();
    window.addEventListener("resize", ajuster);

    return () => {
      window.removeEventListener("resize", ajuster);
      saisie.dispose();
      ws.onclose = null;
      ws.close();
      terminal.dispose();
    };
  }, [id]);

  const message = MESSAGES[etat];
  return (
    <section aria-label="Terminal">
      {message && <p className="etat-terminal">{message}</p>}
      <div className="terminal" ref={conteneur} />
    </section>
  );
}
