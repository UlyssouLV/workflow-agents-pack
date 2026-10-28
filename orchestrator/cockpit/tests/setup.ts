import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { toast } from "sonner";
import { afterEach, beforeEach, vi } from "vitest";
import { FauxMonaco, FauxTerminal, FauxWebSocket } from "./simulations";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./simulations")).FauxTerminal }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./simulations")).FauxFitAddon }));
vi.mock("../src/monaco", async () => ({ monaco: (await import("./simulations")).FauxMonaco }));

beforeEach(() => {
  FauxTerminal.instances = [];
  FauxWebSocket.instances = [];
  FauxMonaco.editeurs = [];
  FauxMonaco.editeursDiff = [];
  FauxMonaco.themes = {};
  sessionStorage.clear();
  vi.stubGlobal("WebSocket", FauxWebSocket);
});

afterEach(() => {
  // Les toasts sonner vivent dans le module : un test ne doit pas voir ceux du précédent.
  toast.dismiss();
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
