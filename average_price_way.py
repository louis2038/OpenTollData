#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, json, math, csv
from collections import defaultdict

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1); phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1); dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))

def load_overpass_lengths(overpass):
    nodes, way_nodes = {}, {}
    for el in overpass.get("elements", []):
        if el.get("type") == "node":
            nodes[int(el["id"])] = (float(el["lat"]), float(el["lon"]))
        elif el.get("type") == "way":
            way_nodes[int(el["id"])] = [int(n) for n in el.get("nodes", [])]
    way_len_km = {}
    for wid, nlist in way_nodes.items():
        d = 0.0
        for i in range(len(nlist)-1):
            u, v = nlist[i], nlist[i+1]
            if u in nodes and v in nodes:
                (lat1,lon1),(lat2,lon2) = nodes[u], nodes[v]
                d += haversine(lat1, lon1, lat2, lon2)
        way_len_km[wid] = d/1000.0
    return way_len_km

def collect_class_keys(price_data):
    keys = set()
    for net in price_data.get("networks", []):
        for dests in net.get("connection", {}).values():
            for payload in dests.values():
                for k in payload.get("price", {}):
                    if k.startswith("class_"): keys.add(k)
    return sorted(keys, key=lambda s: (len(s), s))

class OnlineStats:
    __slots__ = ("count","mean","M2","min","max","sum")
    def __init__(self):
        self.count = 0; self.mean = 0.0; self.M2 = 0.0
        self.min = float("inf"); self.max = float("-inf"); self.sum = 0.0
    def add(self, x):
        self.count += 1; self.sum += x
        if x < self.min: self.min = x
        if x > self.max: self.max = x
        d = x - self.mean
        self.mean += d / self.count
        self.M2 += d * (x - self.mean)
    def variance(self, sample=False):
        if self.count <= (1 if sample else 0): return 0.0
        return self.M2 / ((self.count-1) if sample else self.count)

def compute_stats(enriched, way_len_km, sample=False):
    class_keys = collect_class_keys(enriched)
    stats = defaultdict(lambda: {ck: OnlineStats() for ck in class_keys})
    missing_ways = zero_total = 0

    for net in enriched.get("networks", []):
        for payloads in net.get("connection", {}).values():
            for payload in payloads.values():
                way_ids = payload.get("by_ways", [])
                if not way_ids: continue
                # longueur totale du chemin
                local = []
                total = 0.0
                for wid in way_ids:
                    wid = int(wid)
                    lk = way_len_km.get(wid, 0.0)
                    if wid not in way_len_km: missing_ways += 1
                    local.append((wid, lk)); total += lk
                if total <= 0.0: zero_total += 1; continue
                # contributions par classe
                prices = payload.get("price", {})
                for ck in class_keys:
                    p = float(prices.get(ck, 0.0) or 0.0)
                    if p == 0.0: continue
                    for wid, lk in local:
                        if lk <= 0.0: continue
                        contrib = (lk/total) * p
                        stats[wid][ck].add(contrib)

    if missing_ways or zero_total:
        print(f"[INFO] ways manquantes: {missing_ways}, chemins longueur nulle: {zero_total}")
    return stats, class_keys

def write_csv(stats, way_len_km, class_keys, out_path, sample):
    # Colonnes: way_id, length_km, puis pour chaque classe: count,sum,min,max,mean,variance,mean_per_km
    header = ["way_id","length_km"]
    for ck in class_keys:
        header += [f"{ck}_count",f"{ck}_sum",f"{ck}_min",f"{ck}_max",f"{ck}_mean",f"{ck}_variance",f"{ck}_mean_per_km"]

    with open(out_path,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header); w.writeheader()

        # ⚠️ Filtre: n’imprimer que les ways avec au moins une contribution (>0) sur au moins une classe
        def has_price(wid):
            per = stats.get(wid, {})
            for ck in class_keys:
                st = per.get(ck)
                if st and st.count > 0 and st.sum > 0.0:
                    return True
            return False

        wids = [wid for wid in stats.keys() if has_price(wid)]
        for wid in sorted(wids):
            length = way_len_km.get(wid, 0.0)
            row = {"way_id": wid, "length_km": f"{length:.6f}"}
            per = stats[wid]
            for ck in class_keys:
                st = per.get(ck)
                if not st or st.count == 0:
                    row[f"{ck}_count"]="0"; row[f"{ck}_sum"]=row[f"{ck}_min"]=row[f"{ck}_max"]=row[f"{ck}_mean"]=row[f"{ck}_variance"]=row[f"{ck}_mean_per_km"]="0.000000"
                else:
                    mean = st.mean; var = st.variance(sample=sample)
                    mpk = (mean/length) if length>0 else 0.0
                    row[f"{ck}_count"]=st.count
                    row[f"{ck}_sum"]=f"{st.sum:.6f}"
                    row[f"{ck}_min"]=f"{(st.min if math.isfinite(st.min) else 0.0):.6f}"
                    row[f"{ck}_max"]=f"{(st.max if math.isfinite(st.max) else 0.0):.6f}"
                    row[f"{ck}_mean"]=f"{mean:.6f}"
                    row[f"{ck}_variance"]=f"{var:.6f}"
                    row[f"{ck}_mean_per_km"]=f"{mpk:.6f}"
            w.writerow(row)

def main(argv):
    if len(argv) not in (4,5):
        print("Usage: python stats_prices_per_way.py enriched_price_format.json overpass.json output.csv [--sample]")
        sys.exit(1)
    enriched_path, overpass_path, out_csv = argv[1], argv[2], argv[3]
    sample = (len(argv)==5 and argv[4]=="--sample")

    with open(enriched_path,"r",encoding="utf-8") as f: enriched = json.load(f)
    with open(overpass_path,"r",encoding="utf-8") as f: overpass = json.load(f)

    way_len_km = load_overpass_lengths(overpass)
    stats, class_keys = compute_stats(enriched, way_len_km, sample=sample)
    write_csv(stats, way_len_km, class_keys, out_csv, sample)

    print(f"OK ✓  CSV écrit dans: {out_csv} (only ways avec prix ; variance={'échantillon' if sample else 'population'})")

if __name__ == "__main__":
    main(sys.argv)
