"""Readable views derived solely from the exported object/reference index."""
import collections
from catalog import dump, rows, walk


def generate(destination, records, addressables, containers):
    paths, guids, components = collections.defaultdict(list), {}, collections.defaultdict(list)
    for path, targets in containers.items():
        for target in targets:
            paths[target].append(path)
    for entry in addressables:
        for key in entry["keys"]:
            if isinstance(key, str) and len(key) == 32:
                guids[key] = entry["targets"]
    for record in records.values():
        for ref in record.get("references", []):
            if ref["field"] == "/m_GameObject" and ref["status"] == "resolved":
                components[ref["target"]].append(record["id"])

    def targets(record, field):
        return [r["target"] for r in record.get("references", []) if r["field"] == field and "target" in r]

    def label(identity):
        record = records[identity]
        if record.get("name"):
            return record["name"]
        game_objects = targets(record, "/m_GameObject")
        return records[game_objects[0]].get("name") if game_objects else record.get("script", {}).get("class", identity)

    def item(guid):
        ids = guids.get(guid, [])
        candidate_ids = set(ids)
        for identity in ids:
            candidate_ids.update(components.get(identity, []))
        icons = [records[i] for i in sorted(candidate_ids) if records[i].get("script", {}).get("class") == "Icon_Info"]
        names, tooltips = [], []
        for icon in icons:
            for tooltip in targets(icon, "/_ToolTipText"):
                infos = records[tooltip].get("fields", {}).get("_Infos", [])
                tooltips.extend(infos)
                names.extend(x["_ItemName"] for x in infos if x.get("languageType") == 2 and x.get("_ItemName"))
        return {"guid": guid, "names": sorted(set(names or [label(i) or i for i in ids])),
                "targets": ids, "paths": sorted({p for i in ids for p in paths[i]}),
                "icon_components": [i["id"] for i in icons], "localized_tooltips": tooltips,
                "status": "resolved" if ids else "unresolved"}

    loot_tables, loot_sets, sources, items = [], [], [], []
    set_ids = set()
    for identity, record in sorted(records.items()):
        cls = record.get("script", {}).get("class")
        fields = record.get("fields", {})
        if cls == "Loot_Mgr":
            for table in fields.get("_All_Loot_Icons", []):
                loot_tables.append({"tag": table["_spawnLootTag"], "manager": identity,
                                    "items": [item(ref["m_AssetGUID"]) for ref in table["_all_Icons_Ref"]]})
        if cls == "Loot_Rate_Sets":
            set_ids.add(identity)
            loot_sets.append({"id": identity, "name": label(identity), "rates": fields.get("_LootSpawnRates", [])})
        if cls == "Icon_Info":
            go = targets(record, "/m_GameObject")
            items.append({"id": identity, "name": label(identity), "game_objects": go,
                          "fields": fields, "references": record.get("references", [])})
    for identity, record in sorted(records.items()):
        linked_sets = sorted({r["target"] for r in record.get("references", []) if r.get("target") in set_ids})
        if linked_sets:
            sources.append({"id": identity, "name": label(identity), "class": record.get("script", {}).get("class"),
                            "loot_sets": linked_sets, "fields": record.get("fields", {})})
    loot_tables.sort(key=lambda x: (x["tag"], x["manager"]))
    rows(destination / "views" / "loot-tags.jsonl", loot_tables)
    rows(destination / "views" / "loot-rate-sets.jsonl", loot_sets)
    rows(destination / "views" / "loot-sources.jsonl", sources)
    rows(destination / "views" / "items.jsonl", items)
    rows(destination / "views" / "object-index.jsonl", ({"id": i, "name": label(i), "type": r["type"],
         "class": r.get("script", {}).get("class"), "paths": sorted(paths[i])} for i, r in sorted(records.items())))
    # Subject indexes point to complete records without duplicating large metadata bodies.
    for subject, terms in {"spawns": ("spawn", "biome", "creature_mgr"),
                           "recipes": ("recipe", "craft"),
                           "localization": ("tooltip_text", "language_text")}.items():
        selected = [r for _, r in sorted(records.items()) if r.get("script") and any(
            term in r["script"]["class"].lower() or any(term in k.lower() for k in r.get("fields", {})) for term in terms)]
        rows(destination / "views" / f"{subject}.jsonl", ({"id": r["id"], "name": label(r["id"]),
             "class": r["script"]["class"], "fields": sorted(r.get("fields", {}))} for r in selected))
    lines = ["# Loot tags", "", "Generated from serialized Loot_Mgr records. Item names use English tooltip text when available.",
             "A tag lists eligible items. Spawn rates and source conditions are separate; these are not unconditional drop probabilities.",
             "Displayed rates use six significant digits; the JSON views preserve stored precision.", "",
             "| Tag | Eligible items |", "| --- | ---: |"]
    lines.extend(f"| {table['tag']} | {len(table['items'])} |" for table in loot_tables)
    lines.append("")
    for table in loot_tables:
        tag = table["tag"]
        lines += [f"## {tag}", "", f"Manager: `{table['manager']}`", "", f"Items ({len(table['items'])}):", ""]
        for value in table["items"]:
            lines.append(f"- {', '.join(value['names']) or '[unresolved]'} (`{value['guid']}`)")
        relevant_sets = [s for s in loot_sets if any(r.get("_spawnLootTag") == tag for r in s["rates"])]
        lines += ["", "Loot sets and serialized rate fields:", ""]
        for loot_set in relevant_sets:
            for rate in loot_set["rates"]:
                if rate.get("_spawnLootTag") == tag:
                    spawn_rate = format(rate['_spawnRateRange'], '.6g')
                    stack = format(rate['_stackFactor'], '.6g')
                    lines.append(f"- {loot_set['name']}: _spawnRateRange={spawn_rate}, _stackFactor={stack} (`{loot_set['id']}`)")
        relevant_ids = {s["id"] for s in relevant_sets}
        linked = [s for s in sources if relevant_ids.intersection(s["loot_sets"])]
        lines += ["", "Serialized drop/container sources:", ""]
        lines.extend(f"- {s['name']} ({s['class']}; `{s['id']}`)" for s in linked)
        if not linked:
            lines.append("- No direct serialized source reference found. See runtime code for dynamically assigned sources.")
        lines.append("")
    (destination / "views" / "LOOT.md").write_text("\n".join(lines), encoding="utf-8")
    dump(destination / "views" / "summary.json", {"loot_tables": len(loot_tables), "loot_rate_sets": len(loot_sets),
         "loot_sources": len(sources), "item_components": len(items),
         "unresolved_loot_items": sum(i["status"] != "resolved" for t in loot_tables for i in t["items"])})
