import type { ITerminalOptions, ITheme, Terminal } from "@xterm/xterm";

/** Couleur xterm ← variable de `:root` (index.css). */
const COULEURS: [keyof ITheme, string][] = [
  ["background", "--terminal"],
  ["foreground", "--texte"],
  ["cursor", "--texte"],
  ["cursorAccent", "--terminal"],
  ["selectionBackground", "--terminal-selection"],
  ["black", "--ansi-noir"],
  ["red", "--ansi-rouge"],
  ["green", "--ansi-vert"],
  ["yellow", "--ansi-jaune"],
  ["blue", "--ansi-bleu"],
  ["magenta", "--ansi-magenta"],
  ["cyan", "--ansi-cyan"],
  ["white", "--ansi-blanc"],
  ["brightBlack", "--ansi-vif-noir"],
  ["brightRed", "--ansi-vif-rouge"],
  ["brightGreen", "--ansi-vif-vert"],
  ["brightYellow", "--ansi-vif-jaune"],
  ["brightBlue", "--ansi-vif-bleu"],
  ["brightMagenta", "--ansi-vif-magenta"],
  ["brightCyan", "--ansi-vif-cyan"],
  ["brightWhite", "--ansi-vif-blanc"],
];

function lireVariable(nom: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(nom).trim();
}

/** Thème xterm tiré des variables ; une variable absente laisse la couleur par défaut d’xterm. */
export function themeXterm(lire: (nom: string) => string = lireVariable): ITheme {
  const theme: ITheme = {};
  for (const [cle, variable] of COULEURS) {
    const valeur = lire(variable);
    if (valeur) (theme as Record<string, string>)[cle] = valeur;
  }
  return theme;
}

/** Options communes au terminal en direct et à la relecture : thème, police, curseur. */
export function optionsXterm(): ITerminalOptions {
  const police = lireVariable("--police-mono");
  const taille = parseFloat(lireVariable("--terminal-taille"));
  return {
    theme: themeXterm(),
    ...(police && { fontFamily: police }),
    ...(taille > 0 && { fontSize: taille }),
    cursorBlink: !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  };
}

/** xterm mesure ses cellules à l’ouverture : si la police arrive après, la grille est fausse. Une
 * fois chargée, changer `fontFamily` (aller-retour) lui fait remesurer. */
export function remesurerApresPolice(terminal: Terminal, actif: () => boolean) {
  const police = terminal.options.fontFamily;
  const taille = terminal.options.fontSize;
  if (!police || !taille || !document.fonts) return;
  const font = `${taille}px ${police}`;
  if (document.fonts.check(font)) return;
  void document.fonts.load(font).then(() => {
    if (!actif()) return;
    terminal.options.fontFamily = "monospace";
    terminal.options.fontFamily = police;
  });
}
