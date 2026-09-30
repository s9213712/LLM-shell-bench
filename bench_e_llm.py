import json, time, subprocess, urllib.request, os, glob

BIN = r"C:\Users\s92137\AppData\Local\hermes\runtimes\llamacpp\b10679\cuda"
SERVER = os.path.join(BIN, "llama-server.exe")
PORT = 18900
BASE = f"http://127.0.0.1:{PORT}"
CTX = 98304
SPEED_PROMPT = "用中文寫一段約100字的短文介紹貓"
QUALITY_PROMPT = "請用中文回答:1) 簡述為什麼天空看起來是藍色的;2) 一個常見的誤解是什麼?請指出並更正。"
MT = 200
OUT_FILE = r"C:\Users\s92137\AppData\Local\Temp\claude\bench_results.json"

MODELS = [m for m in sorted(glob.glob(r"E:\LLM\*\*\*.gguf"))
          if "mmproj" not in os.path.basename(m).lower()
          and any(k in os.path.basename(m).lower() for k in ("abliterated", "heretic", "uncensored"))]

def api(path, payload=None, timeout=900):
    data = json.dumps(payload).encode() if payload is not None else None
    return json.loads(urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}), timeout=timeout).read())

def stop(p):
    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
    time.sleep(3)

def gen(prompt, mt=MT):
    t1 = time.time()
    d = api("/v1/chat/completions", {"messages": [{"role": "user", "content": prompt}], "max_tokens": mt})
    el = time.time() - t1
    ct = d.get("usage", {}).get("completion_tokens", 0)
    txt = d.get("choices", [{}])[0].get("message", {}).get("content", "")
    return el, ct, (ct / el if el else 0), txt

def bench(path, extra):
    args = [SERVER, "--model", path, "-c", str(CTX), "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on",
            "-ngl", "99", "-b", "512", "-ub", "512", "--host", "127.0.0.1", "--port", str(PORT),
            "--no-warmup"] + extra
    proc = subprocess.Popen(args, cwd=BIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    up = False
    while time.time() - t0 < 600:
        if proc.poll() is not None:
            break
        try:
            urllib.request.urlopen(BASE + "/health", timeout=3); up = True; break
        except Exception: time.sleep(2)
    if not up:
        stop(proc.pid)
        return None
    load_t = time.time() - t0
    res = {"load_s": round(load_t, 1)}
    try:
        res["cold_s"], res["cold_tok"], res["cold_tps"], _ = gen(SPEED_PROMPT)
        res["warm_s"], res["warm_tok"], res["warm_tps"], _ = gen(SPEED_PROMPT)
        res["qual_s"], res["qual_tok"], res["qual_tps"], res["quality_text"] = gen(QUALITY_PROMPT)
    except Exception as e:
        res["error"] = repr(e)[:150]
    stop(proc.pid)
    return res

results = []
for m in MODELS:
    name = os.path.basename(m)
    row = {"model": name, "GB": round(os.path.getsize(m) / 2**30, 1)}
    attempts = [(["--spec-type", "draft-mtp"], "MTP"), ([], "full-GPU"),
                (["-ot", r".ffn_.*_exps\.=CPU"], "MoE->CPU"), (["-ngl", "40"], "ngl40")]
    for extra, tag in attempts:
        r = bench(m, extra)
        if r is None:
            r = {"error": "server failed to start"}
        if not r.get("error") and "cold_s" in r:
            row["note"] = tag
            row.update(r)
            break
        row.update(r)
    results.append(row)
    print(json.dumps(row, ensure_ascii=False)[:400], flush=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

print("=== SUMMARY ===", flush=True)
for r in results:
    print(f"{r['model'][:55]:55s} {r.get('GB',0):>5}GB {r.get('note','?'):>9} load={r.get('load_s','?'):>6}s cold={r.get('cold_tps','?')} warm={r.get('warm_tps','?')} t/s", flush=True)
print("DONE", flush=True)