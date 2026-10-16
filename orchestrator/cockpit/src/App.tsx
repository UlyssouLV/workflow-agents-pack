import { VueDetail } from "./VueDetail";
import { VueListe } from "./VueListe";

const DETAIL = /^\/repos\/([^/]+)\/([^/]+)\/?$/;

/** Deux routes, servies toutes deux par `index.html` (le runtime) ; les liens rechargent la page. */
export function App({ chemin }: { chemin: string }) {
  const detail = DETAIL.exec(chemin);
  if (detail) {
    return <VueDetail owner={decodeURIComponent(detail[1])} name={decodeURIComponent(detail[2])} />;
  }
  return <VueListe />;
}
