import json, time, subprocess, urllib.request, os, glob

BIN = r"C:\Users\s92137\AppData\Local\hermes\runtimes\llamacpp\b10679\cuda"
SERVER = os.path.join(BIN, "llama-server.exe")
PORT = 18901
BASE = f"http://127.0.0.1:{PORT}"
CTX = 98304
SPEED_PROMPT = "用中文寫一段約100字的短文介紹貓"
QUALITY_PROMPT = "請用中文回答:1) 簡述為什麼天空看起來是藍色的;2) 一個常見的誤解是什麼?請指出並更正。"
OUT_FILE = r"C:\Users\s92137\AppData\Local\Temp\claude\final_results.json"

MODELS = [m for m in sorted(glob.glob(r"E:\LLM\*\*\*.gguf"))
          if "mmproj" not in os.path.basename(m).lower() and "gemma" not in m.lower()
          and any(k in os.path.basename(m).lower() for k in ("abliterated", "heretic", "uncensored"))]

def api(path, payload=None, timeout=900):
    data = json.dumps(payload).encode() if payload is not None else None
    return json.loads(urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}), timeout=timeout).read())

def stop(p):
    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
    time.sleep(3)

def gen(prompt, mt):
    t1 = time.time()
    d = api("/v1/chat/completions", {"messages": [{"role": "user", "content": prompt}], "max_tokens": mt})
    el = time.time() - t1
    msg = d.get("choices", [{}])[0].get("message", {})
    ct = d.get("usage", {}).get("completion_tokens", 0)
    return el, ct, (ct / el if el else 0), msg.get("content", ""), msg.get("reasoning_content", "") or msg.get("reasoning", "")

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
    res = {"load_s": round(time.time() - t0, 1)}
    try:
        res["cold_s"], res["cold_tok"], res["cold_tps"], _, _ = gen(SPEED_PROMPT, 200)
        res["warm_s"], res["warm_tok"], res["warm_tps"], _, _ = gen(SPEED_PROMPT, 200)
        res["qual_s"], res["qual_tok"], res["qual_tps"], res["content"], res["reasoning"] = gen(QUALITY_PROMPT, 400)
    except Exception as e:
        res["error"] = repr(e)[:150]
    stop(proc.pid)
    return res

results = []
for m in MODELS:
    name = os.path.basename(m)
    row = {"model": name, "GB": round(os.path.getsize(m) / 2**30, 1)}
    for extra, tag in [(["--spec-type", "draft-mtp"], "MTP"), ([], "no-MTP"),
                       (["-ot", r".ffn_.*_exps\.=CPU"], "MoE->CPU"), (["-ngl", "40"], "ngl40")]:
        r = bench(m, extra)
        if r is None:
            continue
        if "error" in r:
            continue
        row["note"] = tag
        row.update(r)
        break
    if "note" not in row:
        row["note"] = "FAILED"
    results.append(row)
    print(json.dumps({k: row.get(k) for k in ("model", "GB", "note", "warm_tps", "qual_tps", "error")}, ensure_ascii=False), flush=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

print("=== SUMMARY ===", flush=True)
for r in results:
    print(f"{r['model'][:55]:55s} {r.get('GB',0):>5}GB {r.get('note','?'):>8} warm={r.get('warm_tps','?'):>6} qual={r.get('qual_tps','?'):>6} t/s", flush=True)
print("DONE", flush=True)