import json, time
d = json.load(open("/tmp/fip.json"))
print("top keys:", list(d.keys()))
print("\n=== levels ===")
print(json.dumps(d.get("levels"), indent=1)[:1000])
steps = d["steps"]
now = time.time()
print("\nour clock now =", int(now))
print("=== steps sorted by start ===")
for k, s in sorted(steps.items(), key=lambda x: x[1].get("start", 0)):
    start = s.get("start", 0)
    end = s.get("end", 0)
    dur = end - start
    cur = "  <== NOW" if start <= now <= end else ""
    title = (s.get("title") or "")[:38]
    print("  start=%s end=%s dur=%ss  %r%s" % (start, end, dur, title, cur))
# show all fields of current step
cur = None
for s in steps.values():
    if s.get("start", 0) <= now <= s.get("end", 1e12):
        cur = s
print("\n=== current step ALL fields ===")
if cur:
    for kk, vv in cur.items():
        print("  %s: %s" % (kk, str(vv)[:80]))
