import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { FauxTerminal, FauxWebSocket } from "./simulations";

vi.mock("@xterm/xterm", async () => ({ Terminal: (await import("./simulations")).FauxTerminal }));
vi.mock("@xterm/addon-fit", async () => ({ FitAddon: (await import("./simulations")).FauxFitAddon }));

beforeEach(() => {
  FauxTerminal.instances = [];
  FauxWebSocket.instances = [];
  sessionStorage.clear();
  vi.stubGlobal("WebSocket", FauxWebSocket);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
