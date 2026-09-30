import json, time, subprocess, urllib.request, os, glob, base64

BIN = r"C:\Users\s92137\AppData\Local\hermes\runtimes\llamacpp\b10679\cuda"
SERVER = os.path.join(BIN, "llama-server.exe")
PORT = 18902
BASE = f"http://127.0.0.1:{PORT}"
CTX = 98304
IMG = r"C:\Users\s92137\AppData\Local\Temp\claude\vision_test.png"
VQ = "仔細看這張圖並用中文回答:1) 圖中有哪些形狀?各幾個?顏色?2) 圖中最上面寫了什麼字?"
OUT = r"C:\Users\s92137\AppData\Local\Temp\claude\vision_results.json"

MODELS = [m for m in sorted(glob.glob(r"E:\LLM\*\*\*.gguf"))
          if "mmproj" not in os.path.basename(m).lower() and "gemma" not in m.lower()
          and any(k in os.path.basename(m).lower() for k in ("abliterated", "heretic", "uncensored"))]

def mmproj_for(model_path):
    d = os.path.dirname(model_path)
    hits = glob.glob(os.path.join(d, "mmproj*.gguf"))
    if not hits:
        return None
    # prefer bf16 projector (what Ollama uses)
    for h in hits:
        if "bf16" in h.lower():
            return h
    return hits[0]

def api(path, payload=None, timeout=900):
    data = json.dumps(payload).encode() if payload is not None else None
    return json.loads(urllib.request.urlopen(urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}), timeout=timeout).read())

def stop(p):
    subprocess.run(["taskkill", "/PID", str(p), "/T", "/F"], capture_output=True)
    time.sleep(3)

b64 = base64.b64encode(open(IMG, "rb").read()).decode()

results = []
for m in MODELS:
    name = os.path.basename(m)
    mp = mmproj_for(m)
    row = {"model": name, "mmproj": os.path.basename(mp) if mp else None}
    if not mp:
        row["result"] = "NO MMPROJ"
        results.append(row); print(json.dumps(row), flush=True); continue
    for extra, tag in [(["--spec-type", "draft-mtp"], "MTP"), ([], "no-MTP"), (["-ngl", "40"], "ngl40")]:
        args = [SERVER, "--model", m, "--mmproj", mp, "-c", str(CTX), "-ctk", "q8_0", "-ctv", "q8_0",
                "-fa", "on", "-ngl", "99", "-b", "512", "-ub", "512", "--host", "127.0.0.1",
                "--port", str(PORT), "--no-warmup"] + extra
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
            stop(proc.pid); continue
        row["load_s"] = round(time.time() - t0, 1)
        try:
            t1 = time.time()
            d = api("/v1/chat/completions", {"messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": VQ}]}], "max_tokens": 300})
            row["resp_s"] = round(time.time() - t1, 1)
            msg = d.get("choices", [{}])[0].get("message", {})
            row["tok"] = d.get("usage", {}).get("completion_tokens", 0)
            row["content"] = msg.get("content", "")
            row["reasoning"] = (msg.get("reasoning_content", "") or msg.get("reasoning", ""))[:500]
            row["note"] = tag
        except Exception as e:
            row["error"] = repr(e)[:150]
        stop(proc.pid)
        break
    results.append(row)
    print(json.dumps(row, ensure_ascii=False)[:300], flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
print("VISION DONE", flush=True)