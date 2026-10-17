// Faux xterm.js et faux websocket : jsdom n’a ni canvas ni runtime auquel se connecter.

/** Remplace `Terminal` de `@xterm/xterm` (voir `setup.ts`). */
export class FauxTerminal {
  static instances: FauxTerminal[] = [];
  options: { disableStdin?: boolean; cursorBlink?: boolean };
  cols = 120;
  rows = 30;
  ecrit: Uint8Array[] = [];
  libere = false;
  private saisie: ((donnees: string) => void) | null = null;

  constructor(options: FauxTerminal["options"] = {}) {
    this.options = { ...options };
    FauxTerminal.instances.push(this);
  }

  loadAddon() {}
  open() {}
  focus() {}

  write(donnees: Uint8Array) {
    this.ecrit.push(donnees);
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
    return this.ecrit.map((d) => decodeur.decode(d)).join("");
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
