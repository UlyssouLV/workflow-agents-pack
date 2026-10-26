// Faux xterm.js et faux websocket : jsdom n’a ni canvas ni runtime auquel se connecter.

/** Remplace `Terminal` de `@xterm/xterm` (voir `setup.ts`). */
export class FauxTerminal {
  static instances: FauxTerminal[] = [];
  options: { disableStdin?: boolean; cursorBlink?: boolean; cols?: number; rows?: number };
  cols: number;
  rows: number;
  ecrit: (Uint8Array | string)[] = [];
  libere = false;
  private saisie: ((donnees: string) => void) | null = null;

  constructor(options: FauxTerminal["options"] = {}) {
    this.options = { ...options };
    this.cols = options.cols ?? 120;
    this.rows = options.rows ?? 30;
    FauxTerminal.instances.push(this);
  }

  loadAddon() {}
  open() {}
  focus() {}

  write(donnees: Uint8Array | string) {
    this.ecrit.push(donnees);
  }

  resize(colonnes: number, lignes: number) {
    this.cols = colonnes;
    this.rows = lignes;
  }

  reset() {
    this.ecrit = [];
  }

  onData(rappel: (donnees: string) => void) {
    this.saisie = rappel;
    return { dispose: () => (this.saisie = null) };
  }

  dispose() {
    this.libere = true;
  }

  /** Côté test : ce que l’utilisateur tape (xterm l’émet même en lecture seule). */
  taper(donnees: string) {
    this.saisie?.(donnees);
  }

  /** Côté test : tout ce qui a été affiché. */
  texte(): string {
    const decodeur = new TextDecoder();
    return this.ecrit.map((d) => (typeof d === "string" ? d : decodeur.decode(d))).join("");
  }
}

/** Remplace `FitAddon` de `@xterm/addon-fit`. */
export class FauxFitAddon {
  fit() {}
}

/** Remplace `WebSocket` (voir `setup.ts`) ; le test joue le runtime. */
export class FauxWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;
  static instances: FauxWebSocket[] = [];

  readyState = FauxWebSocket.CONNECTING;
  binaryType = "blob";
  envoyes: unknown[] = [];
  onmessage: ((evenement: MessageEvent) => void) | null = null;
  onclose: ((evenement: CloseEvent) => void) | null = null;

  constructor(readonly url: string) {
    FauxWebSocket.instances.push(this);
  }

  send(donnees: string) {
    this.envoyes.push(JSON.parse(donnees));
  }

  close() {
    this.readyState = FauxWebSocket.CLOSED;
  }

  /** Côté test : le runtime accepte et annonce le rôle. */
  role(role: "ecriture" | "lecture") {
    this.readyState = FauxWebSocket.OPEN;
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify({ role }) }));
  }

  sortie(texte: string) {
    this.onmessage?.(new MessageEvent("message", { data: new TextEncoder().encode(texte).buffer }));
  }

  /** Côté test : le runtime ferme (session finie, ou refus). */
  fermer() {
    this.readyState = FauxWebSocket.CLOSED;
    this.onclose?.(new CloseEvent("close"));
  }
}

/** Modèle de `FauxMonaco` : le contenu et l’URI d’où Monaco déduit le langage. */
export class FauxModele {
  libere = false;
  constructor(
    readonly valeur: string,
    readonly uri: { path: string },
  ) {}

  getValue() {
    return this.valeur;
  }

  dispose() {
    this.libere = true;
  }
}

/** Éditeur de `FauxMonaco`. */
export class FauxEditeur {
  modele: FauxModele | null = null;
  libere = false;
  constructor(readonly options: Record<string, unknown>) {}

  setModel(modele: FauxModele | null) {
    this.modele = modele;
  }

  dispose() {
    this.libere = true;
  }
}

/** Éditeur de diff de `FauxMonaco` : HEAD (`original`) et courant (`modified`). */
export class FauxEditeurDiff {
  modele: { original: FauxModele; modified: FauxModele } | null = null;
  libere = false;
  constructor(readonly options: Record<string, unknown>) {}

  setModel(modele: { original: FauxModele; modified: FauxModele } | null) {
    this.modele = modele;
  }

  dispose() {
    this.libere = true;
  }
}

/** Remplace `monaco` de `src/monaco.ts` (voir `setup.ts`) : jsdom ne fait pas tourner Monaco. */
export const FauxMonaco = {
  editeurs: [] as FauxEditeur[],
  editeursDiff: [] as FauxEditeurDiff[],
  editor: {
    createDiffEditor(_conteneur: HTMLElement, options: Record<string, unknown>) {
      const editeur = new FauxEditeurDiff(options);
      FauxMonaco.editeursDiff.push(editeur);
      return editeur;
    },
    create(_conteneur: HTMLElement, options: Record<string, unknown>) {
      const editeur = new FauxEditeur(options);
      FauxMonaco.editeurs.push(editeur);
      return editeur;
    },
    createModel(valeur: string, _langage: string | undefined, uri: { path: string }) {
      return new FauxModele(valeur, uri);
    },
  },
  Uri: {
    file: (chemin: string) => ({ path: chemin.startsWith("/") ? chemin : `/${chemin}` }),
    from: ({ scheme, path }: { scheme: string; path: string }) => ({ scheme, path }),
  },
};
