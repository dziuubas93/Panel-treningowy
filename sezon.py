#!/usr/bin/env python3
"""Podsumowanie sezonu kolarskiego z intervals.icu -> dashboard.html

Użycie:
  python3 sezon.py            pobiera dane z intervals.icu i buduje dashboard
  python3 sezon.py --offline  buduje z danych zapisanych wcześniej w cache/
  python3 sezon.py --demo     buduje na danych przykładowych (bez klucza API)
"""
import base64
import datetime as dt
import json
import math
import os
import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")
API = "https://intervals.icu/api/v1"

RIDE_TYPES = {"Ride", "VirtualRide", "GravelRide", "MountainBikeRide", "EBikeRide", "TrackRide"}
STRENGTH_TYPES = {"WeightTraining", "Workout", "Crossfit", "Pilates", "Yoga"}

# Bodźce, w kolejności na wykresie
STIMULI = ["baza", "tempo", "prog", "vo2", "beztlen", "sila", "inne"]
STIMULUS_LABEL = {
    "baza": "Baza (Z1-Z2)", "tempo": "Tempo (Z3)", "prog": "Próg (Z4)", "vo2": "VO2max (Z5)",
    "beztlen": "Beztlenowy (Z6-Z7)", "sila": "Siła", "inne": "Inne sporty",
}
# Strefa mocy -> bodziec oraz środek strefy jako ułamek FTP (do rozdziału obciążenia i kJ)
ZONE_STIM = {"Z1": "baza", "Z2": "baza", "Z3": "tempo", "Z4": "prog", "Z5": "vo2", "Z6": "beztlen", "Z7": "beztlen"}
ZONE_MID = {"Z1": 0.45, "Z2": 0.65, "Z3": 0.83, "Z4": 0.98, "Z5": 1.13, "Z6": 1.35, "Z7": 1.8}
HR_ZONE_STIM = ["baza", "baza", "tempo", "prog", "vo2"]

CATEGORIES = ["regeneracja", "baza", "baza długa", "tempo / sst", "próg", "vo2max", "beztlenowy",
              "wyścig / mieszany", "siła", "inne sporty"]


# ---------------------------------------------------------------- pobieranie

def load_env():
    path = os.path.join(HERE, ".env")
    env = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def api_get(path, params, key):
    url = API + path + "?" + urllib.parse.urlencode(params)
    token = base64.b64encode(("API_KEY:" + key).encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": "Basic " + token, "Accept": "application/json",
                                               "User-Agent": "dziubek-panel/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_all(cfg):
    key = load_env().get("INTERVALS_API_KEY") or os.environ.get("INTERVALS_API_KEY")
    if not key:
        sys.exit("Brak klucza. Skopiuj .env.example do .env i wklej INTERVALS_API_KEY (intervals.icu -> Settings -> Developer).")
    aid = load_env().get("INTERVALS_ATHLETE_ID") or os.environ.get("INTERVALS_ATHLETE_ID") or cfg.get("athlete_id", "0")
    od = min([cfg["sezon"]["od"]] + [p["od"] for p in cfg["porownanie"]])
    do = cfg["sezon"]["do"]
    os.makedirs(CACHE, exist_ok=True)
    data = {}

    def step(name, fn):
        try:
            data[name] = fn()
            print("  ok   " + name)
        except urllib.error.HTTPError as e:
            print("  BŁĄD %s: HTTP %s %s" % (name, e.code, e.reason))
            if e.code == 401:
                sys.exit("Klucz API nie działa (401). Sprawdź INTERVALS_API_KEY.")
            if e.code == 403:
                sys.exit("intervals.icu odmówił dostępu (403) – zły INTERVALS_ATHLETE_ID albo blokada zapytania.")
            data[name] = None

    print("Pobieram z intervals.icu…")
    step("athlete", lambda: api_get("/athlete/%s" % aid, {}, key))
    step("activities", lambda: api_get("/athlete/%s/activities" % aid, {"oldest": od, "newest": do}, key))
    step("wellness", lambda: api_get("/athlete/%s/wellness" % aid, {"oldest": od, "newest": do}, key))
    future = (dt.date.today() + dt.timedelta(days=365)).isoformat()
    step("events", lambda: api_get("/athlete/%s/events" % aid, {"oldest": cfg["sezon"]["od"], "newest": future}, key))
    curves = {}
    for p in cfg["porownanie"]:
        try:
            curves[p["nazwa"]] = api_get("/athlete/%s/power-curves" % aid,
                                         {"type": "Ride", "curves": "r.%s.%s" % (p["od"], p["do"])}, key)
            print("  ok   krzywa mocy: " + p["nazwa"])
        except urllib.error.HTTPError as e:
            print("  BŁĄD krzywa mocy %s: HTTP %s" % (p["nazwa"], e.code))
    data["curves"] = curves
    with open(os.path.join(CACHE, "dane.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


# ---------------------------------------------------------------- dane demo

def demo_data(cfg):
    rnd = random.Random(7)
    start = dt.date.fromisoformat(cfg["sezon"]["od"])
    end = min(dt.date.fromisoformat(cfg["sezon"]["do"]), dt.date.today())
    acts, wellness = [], []
    ctl = atl = 15.0
    aid = 1
    d = start
    while d <= end:
        weeks_in = (d - start).days / 7
        load_day = 0
        wd = d.weekday()
        if weeks_in > 8 and wd in (1, 3, 5, 6) and rnd.random() < 0.85:
            long_ride = wd == 6 and rnd.random() < 0.15
            hard = wd in (1, 3) and rnd.random() < 0.8
            dur = rnd.randint(150, 260) * 60 if long_ride else rnd.randint(50, 110) * 60
            z = {"Z1": 0.25, "Z2": 0.6, "Z3": 0.08, "Z4": 0.04, "Z5": 0.02, "Z6": 0.01, "Z7": 0.0}
            if hard:
                kind = rnd.choice(["Z4", "Z5", "Z6", "Z3"])
                z[kind] += 0.25
                z["Z2"] -= 0.2
            secs = [{"id": k, "secs": int(dur * max(v, 0) / sum(z.values()))} for k, v in z.items()]
            iff = 0.62 + (0.15 if hard else 0) + rnd.uniform(-0.04, 0.06)
            race = wd == 5 and rnd.random() < 0.03
            load = int(dur / 3600 * iff * iff * 100)
            name = "Wyścig gravel" if race else (
                "Intervals: Treshold" if hard else rnd.choice(["Endurance: spokojna", "Poranna jazda na rowerze"]))
            acts.append({
                "id": "i%d" % aid, "start_date_local": d.isoformat() + "T10:00:00", "type": rnd.choice(["Ride", "VirtualRide"]),
                "name": name, "moving_time": dur, "distance": dur * rnd.uniform(6, 8),
                "total_elevation_gain": rnd.randint(50, 900), "icu_training_load": load,
                "icu_intensity": iff * 100, "icu_joules": int(dur * 140 * iff / 0.75),
                "icu_zone_times": secs, "race": race, "trainer": False,
            })
            load_day += load
            aid += 1
        if wd in (0, 2) and rnd.random() < 0.75:
            dur = rnd.randint(45, 75) * 60
            acts.append({"id": "i%d" % aid, "start_date_local": d.isoformat() + "T12:00:00", "type": "WeightTraining",
                         "name": "Siłownia", "moving_time": dur, "icu_training_load": rnd.randint(12, 25)})
            aid += 1
        if wd == 4 and rnd.random() < 0.15:
            acts.append({"id": "i%d" % aid, "start_date_local": d.isoformat() + "T18:00:00", "type": "Walk",
                         "name": "Spacer", "moving_time": 3600, "icu_training_load": 10})
            aid += 1
        ctl += (load_day - ctl) / 42
        atl += (load_day - atl) / 7
        wellness.append({"id": d.isoformat(), "ctl": round(ctl, 1), "atl": round(atl, 1), "weight": 55.5})
        d += dt.timedelta(days=1)

    def curve(cp, wp, pmax):
        secs = [1, 5, 15, 30, 60, 120, 180, 300, 480, 600, 720, 1200, 1800, 3600]
        return {"list": [{"secs": secs, "watts": [round(min(pmax, cp + wp / s)) for s in secs]}]}

    names = [p["nazwa"] for p in cfg["porownanie"]]
    curves = {names[0]: curve(140, 8200, 520), names[-1]: curve(158, 11500, 600)}
    events = [{"category": "RACE_A", "name": "Robinsonada Pomorska", "start_date_local": "2026-10-17T09:00:00"}]
    return {"athlete": {"icu_weight": 55.5}, "activities": acts, "wellness": wellness, "events": events, "curves": curves}


# ---------------------------------------------------------------- liczenie

def monday(d):
    return d - dt.timedelta(days=d.weekday())


def act_date(a):
    return dt.date.fromisoformat(a["start_date_local"][:10])


def zone_secs(a):
    """Czas w strefach mocy {Z1..Z7: s}; gdy brak mocy, mapuje strefy tętna."""
    out = {}
    for z in a.get("icu_zone_times") or []:
        if isinstance(z, dict) and z.get("id") in ZONE_STIM:
            out[z["id"]] = out.get(z["id"], 0) + (z.get("secs") or 0)
    if sum(out.values()) > 0:
        return out, "moc"
    hr = a.get("icu_hr_zone_times") or []
    if hr and sum(hr) > 0:
        mapped = {"Z1": 0, "Z3": 0, "Z4": 0, "Z5": 0}
        for i, s in enumerate(hr[:7]):
            mapped[["Z1", "Z1", "Z3", "Z4", "Z5", "Z5", "Z5"][i]] += s
        return mapped, "tętno"
    return {"Z2": a.get("moving_time") or 0}, "brak"


def split_ride(a, weight):
    """Rozdziela obciążenie, czas i kJ/kg jazdy na bodźce."""
    zs, src = zone_secs(a)
    load = a.get("icu_training_load") or 0
    joules = a.get("icu_joules") or 0
    w_load = {z: s * ZONE_MID[z] ** 2 for z, s in zs.items()}
    w_kj = {z: s * ZONE_MID[z] for z, s in zs.items()}
    tl, tk = sum(w_load.values()) or 1, sum(w_kj.values()) or 1
    res = {k: {"load": 0.0, "secs": 0.0, "kjkg": 0.0} for k in STIMULI}
    for z, s in zs.items():
        st = ZONE_STIM[z]
        res[st]["load"] += load * w_load[z] / tl
        res[st]["secs"] += s
        res[st]["kjkg"] += joules / 1000 / weight * w_kj[z] / tk
    return res, zs, src


def classify(a, zs, cfg, race):
    if race:
        return "wyścig / mieszany"
    total = sum(zs.values()) or 1
    hours = (a.get("moving_time") or 0) / 3600
    iff = (a.get("icu_intensity") or 0) / 100
    share = {}
    for z, s in zs.items():
        share[ZONE_STIM[z]] = share.get(ZONE_STIM[z], 0) + s * ZONE_MID[z] ** 2
    tot_w = sum(share.values()) or 1
    share = {k: v / tot_w for k, v in share.items()}
    hard = {k: v for k, v in share.items() if k != "baza" and v >= 0.15}
    if len(hard) >= 3:
        return "wyścig / mieszany"
    if hard:
        top = max(hard, key=hard.get)
        if hard[top] >= 0.25:
            return {"tempo": "tempo / sst", "prog": "próg", "vo2": "vo2max", "beztlen": "beztlenowy"}[top]
    if hours >= cfg["dluga_jazda_godziny"] and (zs.get("Z1", 0) + zs.get("Z2", 0)) / total >= 0.7:
        return "baza długa"
    if 0 < iff < 0.6 and hours < 1.25:
        return "regeneracja"
    return "baza"


def fit_cp(curve):
    """CP i W' z modelu 2-parametrowego: praca = CP*t + W' (odcinki 3–20 min)."""
    pts = [(s, w) for s, w in zip(curve["secs"], curve["watts"]) if 180 <= s <= 1200 and w]
    if len(pts) < 2:
        return None, None
    xs = [s for s, _ in pts]
    ys = [s * w for s, w in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None, None
    cp = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return cp, my - cp * mx


def curve_from(resp):
    if isinstance(resp, dict):
        resp = resp.get("list") or resp.get("curves") or [resp]
    if isinstance(resp, list) and resp and isinstance(resp[0], dict) and resp[0].get("secs"):
        return resp[0]
    return None


def best_at(curve, secs):
    best = None
    for s, w in zip(curve["secs"], curve["watts"]):
        if s >= secs and w:
            return w
        best = w
    return best


def avg_weight(wellness, od, do, fallback):
    ws = [w.get("weight") for w in wellness or [] if od <= w.get("id", "") <= do and w.get("weight")]
    return sum(ws) / len(ws) if ws else fallback


def markers(data, cfg):
    out = []
    for p in cfg["porownanie"]:
        c = curve_from((data.get("curves") or {}).get(p["nazwa"]))
        row = {"nazwa": p["nazwa"], "od": p["od"], "do": p["do"]}
        if c:
            cp, wp = fit_cp(c)
            kg = avg_weight(data.get("wellness"), p["od"], p["do"], cfg["waga_kg"])
            mp = best_at(c, cfg["map_sekundy"])
            row.update({
                "cp": round(cp) if cp else None,
                "aet": round(cp * cfg["aet_jako_procent_cp"]) if cp else None,
                "map": round(mp) if mp else None,
                "vo2": round(10.8 * mp / kg + 7, 1) if mp else None,
                "wprime": round(wp / 1000, 1) if wp else None,
                "p20": best_at(c, 1200),
                "waga": round(kg, 1),
            })
        out.append(row)
    return out


def analyse(data, cfg):
    od = dt.date.fromisoformat(cfg["sezon"]["od"])
    do = dt.date.fromisoformat(cfg["sezon"]["do"])
    weight = (data.get("athlete") or {}).get("icu_weight") or cfg["waga_kg"]
    easy_re = re.compile(cfg["wzorce_spokojnych"], re.I)
    race_re = re.compile(cfg["wzorce_wyscigow"], re.I)
    race_days = {}
    for e in data.get("events") or []:
        if str(e.get("category", "")).startswith("RACE"):
            race_days[(e.get("start_date_local") or "")[:10]] = e.get("name")

    weeks = {}
    w = monday(od)
    while w <= do:
        weeks[w.isoformat()] = {"stim": {k: 0.0 for k in STIMULI}, "z3": [0.0, 0.0, 0.0]}
        w += dt.timedelta(days=7)

    totals = {k: {"load": 0.0, "secs": 0.0, "kjkg": 0.0} for k in STIMULI}
    cats = {c: 0 for c in CATEGORIES}
    ride_secs = strength_secs = 0
    strength_n = 0
    races, long_rides, too_hard, no_power = [], [], [], 0

    for a in sorted(data.get("activities") or [], key=lambda x: x.get("start_date_local", "")):
        d = act_date(a)
        if not (od <= d <= do):
            continue
        wk = weeks.get(monday(d).isoformat())
        typ = a.get("type") or ""
        secs = a.get("moving_time") or 0
        if typ in RIDE_TYPES:
            split, zs, src = split_ride(a, weight)
            if src != "moc":
                no_power += 1
            for k, v in split.items():
                for m in v:
                    totals[k][m] += v[m]
                wk["stim"][k] += v["load"]
            wk["z3"][0] += zs.get("Z1", 0) + zs.get("Z2", 0)
            wk["z3"][1] += zs.get("Z3", 0) + zs.get("Z4", 0)
            wk["z3"][2] += zs.get("Z5", 0) + zs.get("Z6", 0) + zs.get("Z7", 0)
            ride_secs += secs
            name = a.get("name") or ""
            is_race = bool(a.get("race")) or a.get("sub_type") == "RACE" or d.isoformat() in race_days \
                or bool(race_re.search(name))
            cat = classify(a, zs, cfg, is_race)
            cats[cat] += 1
            info = {"data": d.isoformat(), "nazwa": name, "km": round((a.get("distance") or 0) / 1000),
                    "przewyzszenie": round(a.get("total_elevation_gain") or 0), "czas": secs,
                    "np": a.get("icu_weighted_avg_watts"), "if": round((a.get("icu_intensity") or 0) / 100, 2),
                    "obciazenie": a.get("icu_training_load"), "id": a.get("id")}
            if is_race:
                info["nazwa_startu"] = race_days.get(d.isoformat()) or name
                races.append(info)
            if secs >= cfg["dluga_jazda_godziny"] * 3600:
                long_rides.append(dict(info, kategoria=cat))
            total_z = sum(zs.values()) or 1
            above = 1 - (zs.get("Z1", 0) + zs.get("Z2", 0)) / total_z
            if not is_race and easy_re.search(name) and src == "moc" and (
                    info["if"] > cfg["spokojna_za_mocna_if"] or above > cfg["spokojna_za_mocna_procent_powyzej_aet"]):
                too_hard.append(dict(info, powyzej_aet=round(above * 100)))
        else:
            key = "sila" if typ in STRENGTH_TYPES else "inne"
            load = a.get("icu_training_load") or 0
            totals[key]["load"] += load
            totals[key]["secs"] += secs
            wk["stim"][key] += load
            if key == "sila":
                strength_secs += secs
                strength_n += 1
                cats["siła"] += 1
            else:
                cats["inne sporty"] += 1

    total_load = sum(v["load"] for v in totals.values()) or 1
    z3 = [sum(w["z3"][i] for w in weeks.values()) for i in range(3)]
    wel = sorted([w for w in data.get("wellness") or [] if w.get("ctl") is not None], key=lambda x: x["id"])
    wel = [w for w in wel if od.isoformat() <= w["id"] <= do.isoformat()]
    today = dt.date.today().isoformat()
    upcoming = sorted([{"data": (e.get("start_date_local") or "")[:10], "nazwa": e.get("name")}
                       for e in data.get("events") or []
                       if str(e.get("category", "")).startswith("RACE") and (e.get("start_date_local") or "")[:10] >= today
                       and (e.get("start_date_local") or "")[:10] not in {r["data"] for r in races}],
                      key=lambda x: x["data"])

    return {
        "sezon": cfg["sezon"], "wygenerowano": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "waga": weight, "stimuli": STIMULI, "stimulus_label": STIMULUS_LABEL,
        "tygodnie": [{"tydzien": k, **v} for k, v in weeks.items()],
        "bodzce": {k: {"load": round(v["load"]), "pct": round(v["load"] / total_load * 100), "secs": round(v["secs"]),
                       "kjkg": round(v["kjkg"], 1)} for k, v in totals.items()},
        "kategorie": cats,
        "rozklad": z3,
        "kpi": {"rower_h": round(ride_secs / 3600), "sila_h": round(strength_secs / 3600), "sila_n": strength_n,
                "dlugie": len(long_rides), "ponizej_aet": round(z3[0] / (sum(z3) or 1) * 100),
                "ctl_start": wel[0]["ctl"] if wel else None, "ctl_max": max((w["ctl"] for w in wel), default=None),
                "ctl_teraz": wel[-1]["ctl"] if wel else None, "bez_mocy": no_power},
        "ctl": [{"d": w["id"], "ctl": w["ctl"], "atl": w.get("atl")} for w in wel],
        "markery": markers(data, cfg),
        "starty": races, "nadchodzace": upcoming, "dlugie": long_rides, "za_mocne": too_hard,
        "config": {"dluga_h": cfg["dluga_jazda_godziny"], "aet_pct": cfg["aet_jako_procent_cp"],
                   "map_s": cfg["map_sekundy"],
                   "if_max": cfg["spokojna_za_mocna_if"]},
    }


# ---------------------------------------------------------------- start

def main():
    cfg = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))
    cfg["waga_kg"] = cfg.get("waga_kg") or 60
    today = dt.date.today().isoformat()
    for p in [cfg["sezon"]] + cfg["porownanie"]:
        if p["do"] == "dzis":
            p["do"] = today
    args = sys.argv[1:]
    if "--demo" in args:
        data = demo_data(cfg)
    elif "--offline" in args:
        path = os.path.join(CACHE, "dane.json")
        if not os.path.exists(path):
            sys.exit("Brak cache/dane.json – uruchom najpierw bez --offline.")
        data = json.load(open(path, encoding="utf-8"))
    else:
        data = fetch_all(cfg)
    result = analyse(data, cfg)
    if "--demo" in args:
        result["demo"] = True
    tpl = open(os.path.join(HERE, "szablon.html"), encoding="utf-8").read()
    html = tpl.replace("/*__DANE__*/null", json.dumps(result, ensure_ascii=False))
    out = os.path.join(HERE, "dashboard.html")
    open(out, "w", encoding="utf-8").write(html)
    print("Gotowe: " + out)


if __name__ == "__main__":
    main()
