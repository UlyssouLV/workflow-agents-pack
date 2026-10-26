// Monaco sans services de langage : la coloration (Monarch) de tous les langages de base, et le seul
// worker de l’éditeur. Le codespace est en lecture seule : ni complétion ni diagnostics.
import "monaco-editor/basic-languages/monaco.contribution";
import * as monaco from "monaco-editor/editor/editor.api";
import EditorWorker from "monaco-editor/editor/editor.worker?worker";

self.MonacoEnvironment = { getWorker: () => new EditorWorker() };

export { monaco };
