import type { CSSProperties } from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

/** Toasts des confirmations passagères seulement (les erreurs persistantes sont des Alert). */
function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="dark"
      className="toaster group"
      style={
        {
          "--normal-bg": "var(--surface-2)",
          "--normal-text": "var(--texte)",
          "--normal-border": "var(--filet)",
          "--border-radius": "var(--rayon)",
        } as CSSProperties
      }
      {...props}
    />
  );
}

export { Toaster };
