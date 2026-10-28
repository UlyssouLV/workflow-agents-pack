import type { editor } from "monaco-editor/editor/editor.api";
import { lireVariable } from "./themeXterm";

/** Nom sous lequel le codespace déclare son thème (`monaco.editor.defineTheme`). */
export const THEME_MONACO = "hephaistos";

/** Couleur Monaco ← variable de `:root` (index.css). */
const COULEURS: [string, string][] = [
  ["editor.background", "--terminal"],
  ["editorGutter.background", "--terminal"],
  ["editor.foreground", "--texte"],
  ["editorCursor.foreground", "--texte"],
  ["editorLineNumber.foreground", "--faible"],
  ["editorLineNumber.activeForeground", "--attenue"],
  ["editor.lineHighlightBackground", "--surface"],
  ["editor.selectionBackground", "--terminal-selection"],
  ["editorWidget.background", "--surface-2"],
  ["editorWidget.border", "--filet"],
  ["diffEditor.insertedTextBackground", "--diff-ajout"],
  ["diffEditor.insertedLineBackground", "--diff-ajout"],
  ["diffEditor.removedTextBackground", "--diff-retrait"],
  ["diffEditor.removedLineBackground", "--diff-retrait"],
];

/** Thème sombre tiré des variables, la coloration syntaxique de `vs-dark` gardée ; une variable
 * absente laisse la couleur par défaut de Monaco. */
export function themeMonaco(lire: (nom: string) => string = lireVariable): editor.IStandaloneThemeData {
  const colors: Record<string, string> = {};
  for (const [cle, variable] of COULEURS) {
    const valeur = lire(variable);
    if (valeur) colors[cle] = valeur;
  }
  return { base: "vs-dark", inherit: true, rules: [], colors };
}

/** Options communes à l’éditeur de fichier et à l’éditeur de diff : thème et police. */
export function optionsMonaco(): { theme: string; fontFamily?: string; fontSize?: number } {
  const police = lireVariable("--police-mono");
  const taille = parseFloat(lireVariable("--code-taille"));
  return { theme: THEME_MONACO, ...(police && { fontFamily: police }), ...(taille > 0 && { fontSize: taille }) };
}

/** Monaco mesure ses caractères à la création : si la police arrive après, `remesurer` (soit
 * `monaco.editor.remeasureFonts`) une fois chargée. */
export function remesurerApresPolice(options: ReturnType<typeof optionsMonaco>, remesurer: () => void) {
  if (!options.fontFamily || !options.fontSize || !document.fonts) return;
  const font = `${options.fontSize}px ${options.fontFamily}`;
  if (document.fonts.check(font)) return;
  void document.fonts.load(font).then(remesurer);
}
