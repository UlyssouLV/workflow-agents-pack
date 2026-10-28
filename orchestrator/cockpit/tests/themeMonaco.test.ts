import { afterEach, describe, expect, it } from "vitest";
import { optionsMonaco, THEME_MONACO, themeMonaco } from "../src/themeMonaco";

const VARIABLES: Record<string, string> = {
  "--terminal": "#0b0b0d",
  "--texte": "#ededef",
  "--attenue": "#8e8e97",
  "--faible": "#5e5e66",
  "--surface": "#17171a",
  "--surface-2": "#1e1e22",
  "--filet": "#2b2b31",
  "--terminal-selection": "#5b9cf54d",
  "--diff-ajout": "#4cc38a24",
  "--diff-retrait": "#ec5d5724",
};

describe("thème Monaco", () => {
  afterEach(() => document.documentElement.removeAttribute("style"));

  it("sombre, colorations de base gardées, couleurs de l’éditeur et du diff tirées des variables", () => {
    const theme = themeMonaco((nom) => VARIABLES[nom] ?? "");

    expect(theme).toMatchObject({ base: "vs-dark", inherit: true, rules: [] });
    expect(theme.colors).toEqual({
      "editor.background": "#0b0b0d",
      "editorGutter.background": "#0b0b0d",
      "editor.foreground": "#ededef",
      "editorCursor.foreground": "#ededef",
      "editorLineNumber.foreground": "#5e5e66",
      "editorLineNumber.activeForeground": "#8e8e97",
      "editor.lineHighlightBackground": "#17171a",
      "editor.selectionBackground": "#5b9cf54d",
      "editorWidget.background": "#1e1e22",
      "editorWidget.border": "#2b2b31",
      "diffEditor.insertedTextBackground": "#4cc38a24",
      "diffEditor.insertedLineBackground": "#4cc38a24",
      "diffEditor.removedTextBackground": "#ec5d5724",
      "diffEditor.removedLineBackground": "#ec5d5724",
    });
  });

  it("une variable absente laisse la couleur par défaut de Monaco", () => {
    expect(themeMonaco(() => "").colors).toEqual({});
  });

  it("options : le thème, Geist Mono et la taille du code lues dans :root", () => {
    document.documentElement.style.setProperty("--police-mono", ' "Geist Mono", monospace');
    document.documentElement.style.setProperty("--code-taille", "12.5px");

    expect(optionsMonaco()).toEqual({ theme: THEME_MONACO, fontFamily: '"Geist Mono", monospace', fontSize: 12.5 });
  });
});
