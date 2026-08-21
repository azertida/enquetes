#!/usr/bin/env python3
"""
Enquêtes - Séries policières et téléfilms du terroir franco-belges
sur les chaînes francophones belges et françaises.

Deux mécanismes de détection tournent EN PARALLÈLE :

  1. Liste blanche (series.json) : les séries récurrentes, dont le titre
     est stable et connu d'avance. Comparaison par PRÉFIXE normalisé.

  2. Motif « mot-clé + préposition + lieu propre » : les téléfilms du
     terroir, dont le titre est imprévisible mais la FORME reconnaissable.
     Ex. « Meurtres à Sarlat », « Crimes au mont Ventoux ».

Un programme est retenu s'il satisfait l'un OU l'autre.

Limite assumée : un téléfilm inédit au titre hors formule (« Les Bois
hantés ») échappe aux deux. C'est annoncé aux utilisateurs plutôt que
compensé par un filtre bruyant.

Source : XML local généré par iptv-org/epg (grabber Pickx).
Usage : python3 enquetes.py --source=/tmp/pickx_guide.xml
"""

import argparse
import json
import unicodedata
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

# ============================================================
# CONFIGURATION
# ============================================================

WINDOW_DAYS = 7
OUTPUT_FILE = "enquetes.json"
SERIES_FILE = "series.json"

# Chaînes ciblées : nom canonique -> liste de noms d'affichage acceptés
TARGET_CHANNELS = {
    "TF1":       ["TF1", "TF1 HD"],
    "France 2":  ["France 2", "France 2 HD"],
    "France 3":  ["France 3", "France 3 HD"],
    "TV5 Monde": ["TV5 Monde", "TV5MONDE", "TV5 MONDE"],
    "La Une":    ["La Une", "La Une HD", "RTBF La Une"],
    "Tipik":     ["Tipik", "Tipik HD"],
}

# Mots-clés signature des polars du terroir
KEYWORDS = [
    "Meurtres", "Meurtre",
    "Crimes", "Crime",
    "Mystères", "Mystère",
    "Secrets", "Secret",
]

# Prépositions reliant le mot-clé au lieu
PREPOSITIONS = ["à", "au", "aux", "en", "dans", "de", "d'", "du", "des", "sur"]

# Articles et particules tolérés en minuscule entre préposition et lieu propre
INTERMEDIATE_ARTICLES = (
    "le ", "la ", "les ", "l'",
    "mont ", "saint ", "sainte ", "st ", "ste ",
    "val ", "île ", "ile ", "cap ", "lac ", "bois ",
    "pointe ", "baie ", "côte ", "pays ",
)


# ============================================================
# NORMALISATION DES TITRES
# ============================================================

def normalize(s):
    """
    Ramène un titre à une forme comparable :
    minuscules, sans accents, apostrophes uniformisées, espaces tassés.

    « Léo Mattéi » / « Leo Matteï » / « LEO MATTEI » -> « leo mattei »
    """
    if not s:
        return ""
    # Uniformiser les apostrophes typographiques
    s = s.replace("\u2019", "'").replace("\u02bc", "'").replace("`", "'")
    # Décomposer puis retirer les diacritiques
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Minuscules, espaces tassés
    s = " ".join(s.lower().split())
    return s


# ============================================================
# LISTE BLANCHE DES SÉRIES
# ============================================================

def load_series(path=SERIES_FILE):
    """
    Charge series.json et renvoie une liste de tuples
    (titre_affiché, préfixe_normalisé), triée du plus long au plus court.

    Le tri décroissant garantit qu'un titre long l'emporte sur un préfixe
    plus court qui en serait le début.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    for item in data.get("series", []):
        if not item.get("actif", True):
            continue
        titre = (item.get("titre") or "").strip()
        if not titre:
            continue
        entries.append((titre, normalize(titre)))

    entries.sort(key=lambda t: len(t[1]), reverse=True)
    return entries


def match_series(title, subtitle, series_entries):
    """
    Renvoie le titre de la série si le titre OU le sous-titre commence par
    l'un des préfixes de la liste blanche. Sinon None.

    Comparaison par PRÉFIXE, pas par sous-chaîne : « Munch » capte
    « Munch : Le Silence » mais pas « Edvard Munch, la danse de la vie ».
    """
    champs = [normalize(title), normalize(subtitle)]
    for titre_affiche, prefixe in series_entries:
        for champ in champs:
            if not champ:
                continue
            if champ == prefixe or champ.startswith(prefixe + " ") \
               or champ.startswith(prefixe + ":") or champ.startswith(prefixe + ","):
                return titre_affiche
    return None


# ============================================================
# MOTIF « TÉLÉFILM DU TERROIR »
# ============================================================

def title_matches(title):
    """
    Vérifie si le titre suit le motif « mot-clé + préposition + lieu propre ».
    Ex : « Meurtres en Balagne », « Crimes au mont Ventoux ».
    """
    if not title:
        return False

    title_lower = title.lower()

    for kw in KEYWORDS:
        if kw.lower() not in title_lower:
            continue

        idx = title_lower.find(kw.lower())
        after = title[idx + len(kw):].strip()

        for prep in PREPOSITIONS:
            pattern = prep.lower() + " "
            if not after.lower().startswith(pattern):
                continue

            remainder = after[len(prep):].strip()

            for article in INTERMEDIATE_ARTICLES:
                if remainder.lower().startswith(article):
                    remainder = remainder[len(article):].strip()
                    break

            if remainder and remainder[0].isupper():
                return True

    return False


# ============================================================
# LECTURE DU XML
# ============================================================

def load_xml(source_path):
    """Charge un fichier XML local et renvoie l'arbre parsé."""
    print(f"📂 Lecture du fichier : {source_path}")
    with open(source_path, "rb") as f:
        data = f.read()
    print(f"   Taille : {len(data):,} octets")
    return ET.fromstring(data)


def collect_channel_ids(tree):
    """Trouve les IDs XMLTV des chaînes cibles. dict nom -> list[ID]."""
    found = {name: [] for name in TARGET_CHANNELS}

    for channel in tree.findall("channel"):
        ch_id = channel.get("id", "")
        display_names = [(dn.text or "").strip().lower()
                         for dn in channel.findall("display-name")]

        for canonical, variants in TARGET_CHANNELS.items():
            for variant in variants:
                if variant.lower() in display_names:
                    if ch_id and ch_id not in found[canonical]:
                        found[canonical].append(ch_id)
                    break

    return found


def parse_xmltv_date(date_str):
    """Parse une date au format XMLTV. Ex: '20260607211000 +0200'."""
    s = date_str.strip()
    if " " in s:
        dt_part, tz_part = s.split(" ", 1)
        sign = 1 if tz_part[0] == "+" else -1
        hours = int(tz_part[1:3])
        mins = int(tz_part[3:5])
        offset = timezone(timedelta(hours=sign * hours, minutes=sign * mins))
    else:
        dt_part = s
        offset = timezone.utc

    dt = datetime.strptime(dt_part, "%Y%m%d%H%M%S")
    return dt.replace(tzinfo=offset)


# ============================================================
# EXTRACTION DES PROGRAMMES
# ============================================================

def extract_programmes(tree, channel_ids_by_canonical, window_start, window_end,
                       series_entries, no_filter=False):
    """Extrait les programmes correspondant aux critères."""
    id_to_canonical = {}
    for canonical, ids in channel_ids_by_canonical.items():
        for cid in ids:
            id_to_canonical[cid] = canonical

    programmes = []
    series_vues = set()

    for prog in tree.findall("programme"):
        ch_id = prog.get("channel", "")
        if ch_id not in id_to_canonical:
            continue

        try:
            start_dt = parse_xmltv_date(prog.get("start", ""))
            stop_dt = parse_xmltv_date(prog.get("stop", ""))
        except (ValueError, IndexError):
            continue

        if start_dt < window_start or start_dt > window_end:
            continue

        title_el = prog.find("title")
        title = (title_el.text or "").strip() if title_el is not None else ""

        # Sous-titre récupéré AVANT le filtrage : Pickx met parfois le nom
        # de la série dans le sous-titre et l'épisode dans le titre.
        subtitle_el = prog.find("sub-title")
        subtitle = (subtitle_el.text or "").strip() if subtitle_el is not None else ""

        # --- Les deux filtres, en parallèle ---
        serie = match_series(title, subtitle, series_entries)
        terroir = title_matches(title) or title_matches(subtitle)

        if not no_filter and not (serie or terroir):
            continue

        if serie:
            origine = "serie"
            series_vues.add(serie)
        else:
            origine = "telefilm"

        desc_el = prog.find("desc")
        description = (desc_el.text or "").strip() if desc_el is not None else ""

        cat_el = prog.find("category")
        category = (cat_el.text or "").strip() if cat_el is not None else ""

        icon_el = prog.find("icon")
        icon = icon_el.get("src", "") if icon_el is not None else ""

        # Numéro d'épisode. Pickx fournit deux systèmes : « onscreen »
        # (S03E07, directement lisible) et « xmltv_ns » (2.6.0/1, indexé à
        # partir de zéro). L'appli affiche le premier.
        #
        # Les balises <date> et <previously-shown> ont été testées : Pickx
        # ne les renseigne jamais. Inutile d'aller les chercher.
        episode_nums = {}
        for el in prog.findall("episode-num"):
            systeme = el.get("system", "inconnu")
            valeur = (el.text or "").strip()
            if valeur:
                episode_nums[systeme] = valeur

        programmes.append({
            "start": start_dt.isoformat(),
            "stop": stop_dt.isoformat(),
            "channel": id_to_canonical[ch_id],
            "title": title,
            "subtitle": subtitle,
            "description": description,
            "category": category,
            "icon": icon,
            "origine": origine,
            "serie": serie,
            "episode_nums": episode_nums,
        })

    # Déduplication : Pickx répète les programmes sur les variantes HD/SD/+1
    seen = set()
    deduped = []
    for p in programmes:
        key = (p["title"], p["start"], p["channel"])
        if key not in seen:
            seen.add(key)
            deduped.append(p)

    deduped.sort(key=lambda p: (p.get("start") or "9999"))
    return deduped, series_vues


# ============================================================
# MAIN
# ============================================================

def parse_args():
    p = argparse.ArgumentParser(description="Radar des enquêtes franco-belges")
    p.add_argument("--source", required=True,
                   help="Chemin vers le fichier XML local (Pickx via iptv-org)")
    p.add_argument("--series", default=SERIES_FILE,
                   help=f"Chemin vers la liste blanche (défaut : {SERIES_FILE})")
    p.add_argument("--no-filter", action="store_true",
                   help="Désactive tout filtrage (debug)")
    return p.parse_args()


def main():
    args = parse_args()

    series_entries = load_series(args.series)
    print(f"📋 Liste blanche : {len(series_entries)} séries actives")

    tree = load_xml(args.source)
    n_channels = len(tree.findall("channel"))
    n_programmes = len(tree.findall("programme"))
    print(f"   {n_channels} chaînes, {n_programmes} programmes au total")

    channel_ids = collect_channel_ids(tree)

    print("\n📡 Chaînes ciblées :")
    found_canonicals, missing_canonicals = [], []
    for canonical in TARGET_CHANNELS:
        ids = channel_ids[canonical]
        if ids:
            found_canonicals.append(canonical)
            print(f"   ✓ {canonical} : {ids}")
        else:
            missing_canonicals.append(canonical)
            print(f"   ✗ {canonical} : non trouvée")

    now = datetime.now(tz=timezone.utc)
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=WINDOW_DAYS)
    print(f"\n📅 Fenêtre : {window_start.date()} → {window_end.date()}")

    programmes, series_vues = extract_programmes(
        tree, channel_ids, window_start, window_end,
        series_entries, no_filter=args.no_filter
    )

    n_series = sum(1 for p in programmes if p["origine"] == "serie")
    n_telefilms = len(programmes) - n_series
    print(f"\n🎯 Programmes captés : {len(programmes)} "
          f"({n_series} séries, {n_telefilms} téléfilms)")
    for p in programmes:
        marque = "S" if p["origine"] == "serie" else "T"
        print(f"   [{marque}] [{p['start'][:16]}] [{p['channel']}] {p['title']}")

    # Garde-fou : quelles entrées de la liste blanche n'ont rien capté ?
    # Simple ligne de log — utile le jour où une série semble absente.
    jamais_vues = sorted(t for t, _ in series_entries if t not in series_vues)
    if jamais_vues:
        print(f"\n💤 Sans diffusion sur la fenêtre ({len(jamais_vues)}) :")
        print("   " + ", ".join(jamais_vues))

    # Contrôle : si Pickx cessait de fournir les numéros d'épisode, ils
    # disparaîtraient de l'appli sans autre signal. Une ligne suffit.
    if programmes:
        avec_num = sum(1 for p in programmes if p["episode_nums"])
        part = avec_num * 100 // len(programmes)
        alerte = "" if part >= 90 else "   ⚠️  couverture inhabituellement basse"
        print(f"\n🔖 Numéros d'épisode : {avec_num}/{len(programmes)} ({part} %){alerte}")

    output = {
        "generated_at": now.isoformat(),
        "window_start": window_start.date().isoformat(),
        "window_end": window_end.date().isoformat(),
        "source": "Pickx via iptv-org/epg",
        "channels": sorted(found_canonicals),
        "missing_channels": sorted(missing_canonicals),
        "series_count": len(series_entries),
        "count": len(programmes),
        "programmes": programmes,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Généré : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
