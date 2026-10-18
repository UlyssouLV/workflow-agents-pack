import type { Repo } from "./api";

/** Libellés des stops du pilote, pour badge et notification. */
export const LIBELLES_STOP: Record<NonNullable<Repo["pilote_stop"]>, string> = {
  attend: "Réponse attendue",
  humain_requis: "Intervention humaine requise",
  echouee: "Session échouée",
  interrompue: "Session interrompue",
  aucun_eligible: "Aucun ticket éligible",
  echec_lancement: "Échec de lancement",
};

/** Une fois par onglet : `default` → invite le navigateur. */
export async function demanderPermissionNotifications(): Promise<NotificationPermission | null> {
  if (typeof Notification === "undefined") return null;
  if (Notification.permission === "default") return Notification.requestPermission();
  return Notification.permission;
}

/** Une `Notification` par repo dont le stop vient d’apparaître ou de changer. */
export function notifierStops(repos: Repo[], vus: Map<string, string>): void {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  for (const repo of repos) {
    const stop = repo.pilote ? repo.pilote_stop : null;
    const avant = vus.get(repo.slug);
    if (stop && stop !== avant) {
      new Notification(`Pilote : ${repo.nom ?? repo.slug}`, { body: LIBELLES_STOP[stop] });
    }
    if (stop) vus.set(repo.slug, stop);
    else vus.delete(repo.slug);
  }
}
