# -*- coding: utf-8 -*-
# 模型測速填空:DW-Q4_K_S(Ollama 啟動器 + hermes機制)、Qwen-3-VL-8B(hermes機制)
# hermes機制 = llama.cpp FFN全層丟CPU(override-tensor),無MTP,ctx 98304,量 warm 300 tok
import json, time, subprocess, urllib.request, os

BIN = r"C:\Users\s92137\AppData\Local\hermes\runtimes\llamacpp\b10679\cuda"
SERVER = os.path.join(BIN, "llama-server.exe")
OLLAMA = "http://127.0.0.1:11434"
OUT = r"C:\Users\s92137\AppData\Local\Temp\claude\fillin_results.json"
PROMPT = "用中文寫一段約100字的短文介紹貓"
DW = r"E:\LLM\huihui-ai\Huihui-Qwen3.8-27B-abliterated-GGUF\Huihui-Qwen3.8-27B-abliterated-UD-DW-Q4_K_S.gguf"
VL = r"E:\LLM\mradermacher\Qwen-3-VL-8B-Instruct-heretic-GGUF\Qwen-3-VL-8B-Instruct-heretic.f16.gguf"
VL_MMPROJ = r"E:\LLM\mradermacher\Qwen-3-VL-8B-Instruct-heretic-GGUF\Qwen-3-VL-8B-Instruct-heretic.mmproj-f16.gguf"

results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []

def save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

def post(url, payload, timeout=1800):
    return json.loads(urllib.request.urlopen(urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}),
        timeout=timeout).read())

def ollama_unload(name):
    try: post(OLLAMA + "/api/generate", {"model": name, "prompt": "hi", "keep_alive": 0})
    except Exception: pass

def hermes_preset(path, name, port=18900, mm=None):
    # 清場:確認沒有殘留 server
    subprocess.run(["taskkill", "/IM", "llama-server.exe", "/F"], capture_output=True)
    time.sleep(3)
    args = [os.path.join(BIN, "llama-server.exe"), "--model", path, "-c", "98304",
            "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on", "-ngl", "99",
            "-b", "2048", "-ub", "2048",
            "--override-tensor", r"blk\.\d+\.ffn_.*\.weight=CPU",
            "--host", "127.0.0.1", "--port", str(port), "--no-warmup"]
    if mm:
        args += ["--mmproj", mm]
    proc = subprocess.Popen(args, cwd=BIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    base = f"http://127.0.0.1:{port}"
    up = False
    while time.time() - t0 < 900:
        if proc.poll() is not None: break
        try:
            urllib.request.urlopen(base + "/health", timeout=3); up = True; break
        except Exception: time.sleep(2)
    row = {"model": name, "method": "hermes_preset"}
    if not up:
        row["error"] = "server failed to start"
        results.append(row); save(); print(json.dumps(row), flush=True)
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
        return
    row["load_s"] = round(time.time() - t0, 1)
    try:
        post(base + "/v1/chat/completions", {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 4})  # warm
        t1 = time.time()
        d = post(base + "/v1/chat/completions",
                 {"messages": [{"role": "user", "content": PROMPT}], "max_tokens": 300})
        el = time.time() - t1
        ct = d.get("usage", {}).get("completion_tokens", 0)
        row["gen_tok"] = ct
        row["warm_s"] = round(el, 1)
        row["hermes_preset_tps"] = round(ct / el, 2) if el else None
        tim = d.get("timings", {})
        if tim.get("predicted_per_second"):
            row["server_tps"] = round(tim["predicted_per_second"], 2)
    except Exception as e:
        row["error"] = repr(e)[:150]
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
    time.sleep(3)
    results.append(row); save()
    print(json.dumps(row, ensure_ascii=False), flush=True)

def ollama_bench(gguf, name, mm=None):
    ollama_unload(name)
    mf = r"C:\Users\s92137\AppData\Local\Temp\claude\Modelfile.fillin"
    with open(mf, "w", encoding="utf-8") as f:
        f.write(f"FROM {gguf}\n")
        if mm: f.write(f"FROM {mm}\n")
        f.write("PARAMETER num_ctx 98304\nPARAMETER draft_num_predict 3\n")
    r = subprocess.run(["ollama", "create", name, "-f", mf], capture_output=True, text=True)
    row = {"model": name, "method": "ollama_launcher", "GB": round(os.path.getsize(gguf) / 2**30, 1),
           "created": r.returncode == 0}
    if not row["created"]:
        row["err"] = (r.stderr or "")[-200:]
        results.append(row); save(); print(json.dumps(row), flush=True); return
    t0 = time.time()
    d = post(OLLAMA + "/api/generate", {"model": name, "prompt": PROMPT, "stream": False,
                                        "options": {"num_predict": 400}})
    row["load_s"] = round(d.get("load_duration", 0) / 1e9, 1)
    row["prompt_tps"] = round(d["prompt_eval_count"] / (d["prompt_eval_duration"] / 1e9), 1) if d.get("prompt_eval_count") else None
    n = d.get("eval_count", 0)
    row["gen_tok"] = n
    row["tps"] = round(n / (d["eval_duration"] / 1e9), 2) if d.get("eval_duration") else None
    row["total_s"] = round(time.time() - t0, 1)
    results.append(row); save()
    print(json.dumps(row, ensure_ascii=False), flush=True)
    ollama_unload(name)
    time.sleep(3)

# 1) DW-Q4_K_S 經 Ollama 啟動器
if not any(r.get("model") == "dw-q4ks-ollama" for r in results):
    ollama_bench(DW, "dw-q4ks-ollama")

# 2) DW-Q4_K_S 經 hermes 機制
if not any(r.get("model") == "DW-Q4_K_S" and "hermes_preset_tps" in r for r in results):
    hermes_preset(DW, "DW-Q4_K_S")

# 3) Qwen-3-VL-8B 經 hermes 機制(帶 mmproj)
if not any(r.get("model") == "Qwen-3-VL-8B" and "hermes_preset_tps" in r for r in results):
    hermes_preset(VL, "Qwen-3-VL-8B", mm=VL_MMPROJ)

print("FILLIN DONE", flush=True)