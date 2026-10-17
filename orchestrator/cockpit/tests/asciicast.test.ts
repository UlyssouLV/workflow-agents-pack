import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Lecteur, PAUSE_MAX_MS, lireCast } from "../src/asciicast";
import type { EtatLecture } from "../src/asciicast";
import { FauxTerminal } from "./simulations";

const CAST = [
  JSON.stringify({ version: 2, width: 100, height: 20, timestamp: 1792227600 }),
  JSON.stringify([0.5, "o", "a"]),
  JSON.stringify([0.75, "r", "90x30"]),
  JSON.stringify([60, "o", "b"]),
  "",
].join("\n");

describe("lireCast", () => {
  it("rend la taille de l’en-tête et les événements", () => {
    expect(lireCast(CAST)).toEqual({
      largeur: 100,
      hauteur: 20,
      evenements: [
        [0.5, "o", "a"],
        [0.75, "r", "90x30"],
        [60, "o", "b"],
      ],
    });
  });

  it("une session interrompue en pleine écriture : la dernière ligne coupée est ignorée", () => {
    const coupe = `${CAST}[61, "o", "c`;

    expect(lireCast(coupe).evenements).toHaveLength(3);
  });

  it.each([["", "vide"], ['{"version": 1}', "version 1"], ["pas du json", "illisible"]])(
    "refuse ce qui n’est pas un asciicast v2 (%s)",
    (texte) => {
      expect(() => lireCast(texte)).toThrow("enregistrement illisible");
    },
  );
});

describe("lecteur", () => {
  let etats: EtatLecture[];
  let terminal: FauxTerminal;
  let lecteur: Lecteur;

  beforeEach(() => {
    vi.useFakeTimers();
    etats = [];
    terminal = new FauxTerminal();
    lecteur = new Lecteur(terminal, lireCast(CAST), (etat) => etats.push(etat));
  });

  afterEach(() => lecteur.liberer());

  it("rejoue au rythme enregistré, une longue attente ramenée à une seconde", () => {
    lecteur.jouer();
    expect(etats).toEqual(["lecture"]);

    vi.advanceTimersByTime(499);
    expect(terminal.texte()).toBe("");
    vi.advanceTimersByTime(1);
    expect(terminal.texte()).toBe("a");
    vi.advanceTimersByTime(250);
    expect([terminal.cols, terminal.rows]).toEqual([90, 30]);
    vi.advanceTimersByTime(PAUSE_MAX_MS - 1);
    expect(terminal.texte()).toBe("a");
    vi.advanceTimersByTime(1);
    expect(terminal.texte()).toBe("ab");
    expect(etats).toEqual(["lecture", "fini"]);
  });

  it("pause puis reprise", () => {
    lecteur.jouer();
    vi.advanceTimersByTime(500);
    lecteur.pause();
    vi.advanceTimersByTime(10_000);
    expect(terminal.texte()).toBe("a");

    lecteur.jouer();
    vi.advanceTimersByTime(10_000);

    expect(terminal.texte()).toBe("ab");
    expect(etats).toEqual(["lecture", "pause", "lecture", "fini"]);
  });

  it("aller à la fin écrit tout de suite le reste", () => {
    lecteur.jouer();

    lecteur.finir();

    expect(terminal.texte()).toBe("ab");
    expect(etats.at(-1)).toBe("fini");
    vi.advanceTimersByTime(10_000);
    expect(terminal.texte()).toBe("ab");
  });

  it("rejouer repart de zéro, à la taille enregistrée", () => {
    lecteur.finir();

    lecteur.rejouer();

    expect(terminal.texte()).toBe("");
    expect([terminal.cols, terminal.rows]).toEqual([100, 20]);
    vi.advanceTimersByTime(10_000);
    expect(terminal.texte()).toBe("ab");
  });

  it("libérer arrête la lecture et le terminal", () => {
    lecteur.jouer();

    lecteur.liberer();
    vi.advanceTimersByTime(10_000);

    expect(terminal.texte()).toBe("");
    expect(terminal.libere).toBe(true);
  });
});
