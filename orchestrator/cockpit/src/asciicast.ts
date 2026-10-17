// Relecture d’un terminal enregistré par le runner (`terminal.cast`, asciinema v2).

/** `[secondes depuis le début, "o" (sortie) | "r" (taille « COLSxLIGNES »), données]`. */
export type Evenement = [number, string, string];

export interface Cast {
  largeur: number;
  hauteur: number;
  evenements: Evenement[];
}

/** Une attente plus longue (l’agent réfléchit, personne ne tape) est ramenée à ce délai. */
export const PAUSE_MAX_MS = 1_000;

export function lireCast(texte: string): Cast {
  const [premiere, ...lignes] = texte.split("\n");
  let entete: { version?: number; width?: number; height?: number };
  try {
    entete = JSON.parse(premiere);
  } catch {
    throw new Error("enregistrement illisible");
  }
  if (entete?.version !== 2 || !entete.width || !entete.height) {
    throw new Error("enregistrement illisible");
  }
  const evenements: Evenement[] = [];
  for (const ligne of lignes) {
    if (!ligne.trim()) continue;
    try {
      evenements.push(JSON.parse(ligne) as Evenement);
    } catch {
      // Dernière ligne coupée : le runner a été arrêté en pleine écriture.
      break;
    }
  }
  return { largeur: entete.width, hauteur: entete.height, evenements };
}

/** Ce dont le lecteur a besoin du terminal xterm.js. */
export interface Ecran {
  write(donnees: string): void;
  resize(colonnes: number, lignes: number): void;
  reset(): void;
  dispose(): void;
}

export type EtatLecture = "lecture" | "pause" | "fini";

/** Rejoue les événements dans l’écran, au rythme enregistré (attentes plafonnées). */
export class Lecteur {
  private suivant = 0;
  private minuteur: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly ecran: Ecran,
    private readonly cast: Cast,
    private readonly signaler: (etat: EtatLecture) => void,
  ) {}

  jouer() {
    this.arreter();
    this.signaler("lecture");
    this.planifier();
  }

  pause() {
    this.arreter();
    this.signaler("pause");
  }

  /** Tout le reste, tout de suite. */
  finir() {
    this.arreter();
    while (this.suivant < this.cast.evenements.length) this.appliquer(this.cast.evenements[this.suivant++]);
    this.signaler("fini");
  }

  rejouer() {
    this.arreter();
    this.ecran.reset();
    this.ecran.resize(this.cast.largeur, this.cast.hauteur);
    this.suivant = 0;
    this.jouer();
  }

  liberer() {
    this.arreter();
    this.ecran.dispose();
  }

  private planifier() {
    const { evenements } = this.cast;
    if (this.suivant >= evenements.length) {
      this.signaler("fini");
      return;
    }
    const avant = this.suivant > 0 ? evenements[this.suivant - 1][0] : 0;
    const delai = Math.min(Math.max(0, evenements[this.suivant][0] - avant) * 1000, PAUSE_MAX_MS);
    this.minuteur = setTimeout(() => {
      this.minuteur = null;
      this.appliquer(evenements[this.suivant++]);
      this.planifier();
    }, delai);
  }

  private arreter() {
    if (this.minuteur !== null) clearTimeout(this.minuteur);
    this.minuteur = null;
  }

  private appliquer([, type, donnees]: Evenement) {
    if (type === "o") {
      this.ecran.write(donnees);
    } else if (type === "r") {
      const [colonnes, lignes] = donnees.split("x").map(Number);
      if (colonnes > 0 && lignes > 0) this.ecran.resize(colonnes, lignes);
    }
  }
}
