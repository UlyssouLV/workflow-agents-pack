import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { useEffect, useRef, useState } from "react";
import { lireEnregistrement } from "./api";
import type { EtatLecture } from "./asciicast";
import { Lecteur, lireCast } from "./asciicast";

/** Relecture d’une session finie : son `terminal.cast` rejoué dans xterm.js, sans saisie. */
export function RelectureTerminal({ id }: { id: string }) {
  const conteneur = useRef<HTMLDivElement>(null);
  const lecteur = useRef<Lecteur | null>(null);
  const [etat, setEtat] = useState<EtatLecture | null>(null);
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    let actif = true;
    lireEnregistrement(id)
      .then(lireCast)
      .then(
        (cast) => {
          if (!actif) return;
          const terminal = new Terminal({ disableStdin: true, cols: cast.largeur, rows: cast.hauteur });
          terminal.open(conteneur.current!);
          lecteur.current = new Lecteur(terminal, cast, (e) => actif && setEtat(e));
          lecteur.current.jouer();
        },
        (e: Error) => actif && setErreur(e.message),
      );
    return () => {
      actif = false;
      lecteur.current?.liberer();
      lecteur.current = null;
    };
  }, [id]);

  return (
    <section aria-label="Relecture">
      {erreur && <p className="erreur">{erreur}</p>}
      {etat && (
        <p>
          {etat === "lecture" && (
            <button type="button" onClick={() => lecteur.current?.pause()}>
              Pause
            </button>
          )}
          {etat === "pause" && (
            <button type="button" onClick={() => lecteur.current?.jouer()}>
              Reprendre
            </button>
          )}{" "}
          {etat === "fini" ? (
            <button type="button" onClick={() => lecteur.current?.rejouer()}>
              Rejouer
            </button>
          ) : (
            <button type="button" onClick={() => lecteur.current?.finir()}>
              Aller à la fin
            </button>
          )}
        </p>
      )}
      {!erreur && <div className="terminal relecture" ref={conteneur} />}
    </section>
  );
}
