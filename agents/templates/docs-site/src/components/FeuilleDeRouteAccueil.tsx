import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import clsx from 'clsx';

import feuille from '../data/feuille-de-route.json';
import styles from './feuilleDeRoute.module.css';

type Lien = {titre: string; href: string};

type Version = {
  /** null quand la feuille porte des numéros de développement (rôle livrables). */
  version: string | null;
  titre: string;
  resume: string;
  href: string;
  slug: string;
  /** null quand la feuille n’a pas encore de rubrique « Bloquée par ». */
  etat?: 'ouvrable' | 'bloquee' | null;
  /** Versions qui la bloquent encore. */
  attend?: Lien[];
  prochaine?: boolean;
};

type Donnees = {
  versions: Version[];
  plusTard: string[];
};

const donnees = feuille as Donnees;

export default function FeuilleDeRouteAccueil(): ReactNode {
  if (donnees.versions.length === 0) {
    return (
      <p className={styles.vide}>
        Feuille de route indisponible — lance{' '}
        <code>npm run generer-feuille-de-route</code>.
      </p>
    );
  }

  const avecEtats = donnees.versions.some((v) => v.etat);
  const estProchaine = (v: Version, index: number) =>
    avecEtats ? Boolean(v.prochaine) : index === 0;
  const ouvrables = donnees.versions.filter((v) => v.etat === 'ouvrable');

  return (
    <div className={styles.bloc}>
      {avecEtats ? (
        <div className={styles.ouvrables}>
          <p className={styles.ouvrablesTitre}>
            {ouvrables.length > 1 ? 'Ouvrables maintenant' : ouvrables.length ? 'Ouvrable maintenant' : 'Aucune version ouvrable'}
          </p>
          <ul className={styles.ouvrablesListe}>
            {ouvrables.map((v) => (
              <li key={v.slug}>
                <Link to={v.href}>{v.version ? `${v.version} — ${v.titre}` : v.titre}</Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <ol className={styles.liste}>
        {donnees.versions.map((v, index) => (
          <li key={v.slug}>
            <Link
              className={clsx(
                styles.carte,
                estProchaine(v, index) && styles.carteProchaine,
                v.etat === 'bloquee' && styles.carteBloquee,
              )}
              to={v.href}>
              <div className={styles.bandeau}>
                {v.version ? <span className={styles.badge}>{v.version}</span> : null}
                {estProchaine(v, index) && <span className={styles.prochaine}>Prochaine</span>}
                {v.etat === 'ouvrable' && <span className={styles.etatOuvrable}>Ouvrable</span>}
                {v.etat === 'bloquee' && <span className={styles.etatBloquee}>Bloquée</span>}
              </div>
              <h3 className={styles.titre}>{v.titre}</h3>
              {v.resume ? <p className={styles.resume}>{v.resume}</p> : null}
              {v.attend && v.attend.length > 0 ? (
                <p className={styles.attend}>
                  En attente de : {v.attend.map((b) => b.titre).join(' · ')}
                </p>
              ) : null}
              <span className={styles.lire}>Lire la proposition →</span>
            </Link>
          </li>
        ))}
      </ol>
      {donnees.plusTard.length > 0 ? (
        <div className={styles.plusTard}>
          <p className={styles.plusTardTitre}>Plus tard</p>
          <ul className={styles.chips}>
            {donnees.plusTard.map((sujet) => (
              <li key={sujet} className={styles.chip}>
                {sujet}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
