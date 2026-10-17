"""Enregistrement d’une session : `terminal.cast` (asciinema v2) et transcription de l’agent."""

import json
import os
import time

import pytest

from wap_runtime.enregistrement import Cast, copier_transcription


def lire_cast(chemin):
    entete, *evenements = (json.loads(l) for l in chemin.read_text().splitlines())
    return entete, evenements


def test_le_cast_a_l_en_tete_v2_puis_un_evenement_par_ligne(tmp_path):
    chemin = tmp_path / "terminal.cast"

    with Cast(chemin, 120, 30) as cast:
        cast.sortie(b"bonjour\r\n")
        cast.taille(100, 40)

    entete, evenements = lire_cast(chemin)
    assert entete["version"] == 2
    assert (entete["width"], entete["height"]) == (120, 30)
    assert isinstance(entete["timestamp"], int)
    assert [e[1:] for e in evenements] == [["o", "bonjour\r\n"], ["r", "100x40"]]
    assert all(isinstance(e[0], float) and e[0] >= 0 for e in evenements)
    assert evenements[0][0] <= evenements[1][0]


def test_le_cast_est_lisible_pendant_la_session(tmp_path):
    chemin = tmp_path / "terminal.cast"

    with Cast(chemin, 80, 24) as cast:
        cast.sortie(b"en cours")

        _, evenements = lire_cast(chemin)
        assert evenements[0][1:] == ["o", "en cours"]


def test_un_caractere_coupe_entre_deux_lectures_reste_entier(tmp_path):
    chemin = tmp_path / "terminal.cast"
    octets = "é".encode()

    with Cast(chemin, 80, 24) as cast:
        cast.sortie(b"caf" + octets[:1])
        cast.sortie(octets[1:])

    _, evenements = lire_cast(chemin)
    assert "".join(e[2] for e in evenements) == "café"


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


def ecrire(chemin, contenu="{}\n", age=0.0):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu)
    if age:
        os.utime(chemin, (time.time() - age, time.time() - age))
    return chemin


def test_transcription_claude_ecrite_pendant_la_session_copiee(home, tmp_path):
    projets = home / ".claude" / "projects" / "-clones-o-r"
    ecrire(projets / "ancienne.jsonl", age=3600)
    debut = time.time() - 60
    ecrire(projets / "abc.jsonl", '{"type": "user"}\n')
    ecrire(projets / "abc" / "subagents" / "s1.jsonl")
    cible = tmp_path / "jobs" / "id" / "transcription"

    copiees = copier_transcription("claude", home, debut, cible)

    assert sorted(p.relative_to(cible).as_posix() for p in copiees) == [
        "-clones-o-r/abc.jsonl",
        "-clones-o-r/abc/subagents/s1.jsonl",
    ]
    assert (cible / "-clones-o-r" / "abc.jsonl").read_text() == '{"type": "user"}\n'


def test_transcription_cursor_copiee(home, tmp_path):
    projet = home / ".cursor" / "projects" / "clones-o-r"
    debut = time.time() - 60
    ecrire(projet / "agent-transcripts" / "c1" / "c1.jsonl")
    ecrire(projet / "terminals" / "1.txt")
    cible = tmp_path / "transcription"

    copiees = copier_transcription("cursor", home, debut, cible)

    assert [p.relative_to(cible).as_posix() for p in copiees] == ["clones-o-r/agent-transcripts/c1/c1.jsonl"]


def test_aucune_transcription_rien_n_est_cree(home, tmp_path):
    cible = tmp_path / "transcription"

    assert copier_transcription("claude", home, time.time(), cible) == []
    assert not cible.exists()
