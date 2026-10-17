import { useEffect, useState } from "react";
import { lire } from "./api";

/** Même cadence que le cache de la liste côté runtime (`CACHE_SECONDES`). */
export const RAFRAICHISSEMENT_MS = 60_000;

export interface Lecture<T> {
  donnees: T | null;
  erreur: string | null;
}

/** `chemin` lu au montage puis toutes les `intervalle` ms ; garde la dernière réponse. */
export function useRafraichi<T>(chemin: string, intervalle = RAFRAICHISSEMENT_MS): Lecture<T> {
  const [lecture, setLecture] = useState<Lecture<T>>({ donnees: null, erreur: null });

  useEffect(() => {
    let actif = true;
    const relire = () =>
      lire<T>(chemin).then(
        (donnees) => actif && setLecture({ donnees, erreur: null }),
        (erreur: Error) => actif && setLecture((avant) => ({ ...avant, erreur: erreur.message })),
      );
    void relire();
    const minuteur = setInterval(relire, intervalle);
    return () => {
      actif = false;
      clearInterval(minuteur);
    };
  }, [chemin, intervalle]);

  return lecture;
}
