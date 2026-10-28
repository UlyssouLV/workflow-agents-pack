import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { ClockIcon, FastForwardIcon, PauseIcon, PlayIcon, RotateCcwIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { lireEnregistrement } from "./api";
import type { EtatLecture } from "./asciicast";
import { Lecteur, lireCast } from "./asciicast";
import { Erreur } from "./commun";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { optionsXterm, remesurerApresPolice } from "./themeXterm";

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
          const terminal = new Terminal({
            ...optionsXterm(),
            cursorBlink: false,
            disableStdin: true,
            cols: cast.largeur,
            rows: cast.hauteur,
          });
          terminal.open(conteneur.current!);
          remesurerApresPolice(terminal, () => actif);
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
    <section aria-label="Relecture" className="grid gap-3">
      {erreur && <Erreur>{erreur}</Erreur>}
      {!erreur && (
        <div className="overflow-hidden rounded-lg border bg-terminal">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-card px-3 py-2 text-[12.5px]">
            <Badge variant="neutre">
              <ClockIcon aria-hidden />
              Relecture
            </Badge>
            <span className="text-muted-foreground">Enregistrement de la session (terminal.cast).</span>
          </div>
          {/* Grille fixe de l’enregistrement : plus large qu’un téléphone, elle défile ici, pas la page. */}
          <div className="overflow-x-auto p-2">
            <div className="w-fit" ref={conteneur} />
          </div>
          {etat && (
            <div className="flex flex-wrap items-center gap-2 border-t bg-card px-3.5 py-2.5">
              {etat === "lecture" && (
                <Button variant="outline" size="sm" onClick={() => lecteur.current?.pause()}>
                  <PauseIcon aria-hidden />
                  Pause
                </Button>
              )}
              {etat === "pause" && (
                <Button variant="outline" size="sm" onClick={() => lecteur.current?.jouer()}>
                  <PlayIcon aria-hidden />
                  Reprendre
                </Button>
              )}
              {etat === "fini" ? (
                <Button variant="outline" size="sm" onClick={() => lecteur.current?.rejouer()}>
                  <RotateCcwIcon aria-hidden />
                  Rejouer
                </Button>
              ) : (
                <Button variant="ghost" size="sm" onClick={() => lecteur.current?.finir()}>
                  <FastForwardIcon aria-hidden />
                  Aller à la fin
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
