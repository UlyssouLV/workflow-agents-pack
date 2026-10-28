import { afterEach, describe, expect, it } from "vitest";
import { optionsXterm, themeXterm } from "../src/themeXterm";

const VARIABLES: Record<string, string> = {
  "--terminal": "#0b0b0d",
  "--texte": "#ededef",
  "--terminal-selection": "#5b9cf54d",
  "--ansi-noir": "#26262b",
  "--ansi-rouge": "#ec5d57",
  "--ansi-vert": "#4cc38a",
  "--ansi-jaune": "#e5b454",
  "--ansi-bleu": "#5b9cf5",
  "--ansi-magenta": "#a094f0",
  "--ansi-cyan": "#5ec4d6",
  "--ansi-blanc": "#d6d6db",
  "--ansi-vif-noir": "#5e5e66",
  "--ansi-vif-rouge": "#ff7b74",
  "--ansi-vif-vert": "#6fdba5",
  "--ansi-vif-jaune": "#f2cb7a",
  "--ansi-vif-bleu": "#82b4f8",
  "--ansi-vif-magenta": "#bbb2f5",
  "--ansi-vif-cyan": "#86d6e4",
  "--ansi-vif-blanc": "#ffffff",
};

describe("thème xterm", () => {
  afterEach(() => document.documentElement.removeAttribute("style"));

  it("fond, texte, curseur, sélection et 16 couleurs ANSI viennent des variables", () => {
    const theme = themeXterm((nom) => VARIABLES[nom] ?? "");

    expect(theme).toEqual({
      background: "#0b0b0d",
      foreground: "#ededef",
      cursor: "#ededef",
      cursorAccent: "#0b0b0d",
      selectionBackground: "#5b9cf54d",
      black: "#26262b",
      red: "#ec5d57",
      green: "#4cc38a",
      yellow: "#e5b454",
      blue: "#5b9cf5",
      magenta: "#a094f0",
      cyan: "#5ec4d6",
      white: "#d6d6db",
      brightBlack: "#5e5e66",
      brightRed: "#ff7b74",
      brightGreen: "#6fdba5",
      brightYellow: "#f2cb7a",
      brightBlue: "#82b4f8",
      brightMagenta: "#bbb2f5",
      brightCyan: "#86d6e4",
      brightWhite: "#ffffff",
    });
  });

  it("une variable absente laisse la couleur par défaut d’xterm", () => {
    expect(themeXterm(() => "")).toEqual({});
  });

  it("lit les variables de :root et la police Geist Mono", () => {
    document.documentElement.style.setProperty("--terminal", " #010203");
    document.documentElement.style.setProperty("--police-mono", '"Geist Mono", monospace');

    const options = optionsXterm();

    expect(options.theme?.background).toBe("#010203");
    expect(options.fontFamily).toBe('"Geist Mono", monospace');
  });
});
