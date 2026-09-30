import json, time, subprocess, urllib.request, os

OLLAMA_URL = "http://127.0.0.1:11434"
OUT = r"C:\Users\s92137\AppData\Local\Temp\claude\ollama_all_results.json"

# (model_name, main_gguf, mmproj or None)
MODELS = [
    ("huihui-27b-q3xl", r"E:\LLM\huihui-ai\Huihui-Qwen3.8-27B-abliterated-GGUF\Huihui-Qwen3.8-27B-abliterated-UD-Q3_K_XL.gguf", None),
    ("huihui-27b-q4xl", r"E:\LLM\huihui-ai\Huihui-Qwen3.8-27B-abliterated-GGUF\Huihui-Qwen3.8-27B-abliterated-UD-Q4_K_XL.gguf", None),
    ("cyberstrike-35b", r"E:\LLM\huihui-ai\Huihui-CyberStrike-OffSec-35B-abliterated-GGUF\Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K.gguf",
     r"E:\LLM\huihui-ai\Huihui-CyberStrike-OffSec-35B-abliterated-GGUF\mmproj-model-bf16.gguf"),
    ("qwen35-9b-unc", r"E:\LLM\HauhauCS\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf",
     r"E:\LLM\HauhauCS\Qwen3.5-9B-Uncensored-HauhauCS-Aggressive\mmproj-Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-BF16.gguf"),
    ("qwen3-vl-8b-heretic", r"E:\LLM\mradermacher\Qwen-3-VL-8B-Instruct-heretic-GGUF\Qwen-3-VL-8B-Instruct-heretic.f16.gguf",
     r"E:\LLM\mradermacher\Qwen-3-VL-8B-Instruct-heretic-GGUF\Qwen-3-VL-8B-Instruct-heretic.mmproj-f16.gguf"),
]

def post(path, payload, timeout=1800):
    resp = urllib.request.urlopen(urllib.request.Request(OLLAMA_URL + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}), timeout=timeout)
    body = resp.read().decode()
    return json.loads(body) if body.strip() else {}

results = []
for name, gguf, mm in MODELS:
    row = {"model": name, "GB": round(os.path.getsize(gguf) / 2**30, 1)}
    mf = r"C:\Users\s92137\AppData\Local\Temp\claude\Modelfile.bench"
    with open(mf, "w", encoding="utf-8") as f:
        f.write(f"FROM {gguf}\n")
        if mm:
            f.write(f"FROM {mm}\n")
        f.write("PARAMETER num_ctx 98304\nPARAMETER draft_num_predict 3\n")
    r = subprocess.run(["ollama", "create", name, "-f", mf], capture_output=True, text=True)
    row["created"] = r.returncode == 0
    if not row["created"]:
        row["err"] = (r.stderr or "")[-200:]
        results.append(row); print(json.dumps(row), flush=True); continue
    # timed generation, then unload
    t0 = time.time()
    d = post("/api/generate", {"model": name, "prompt": "用中文寫一段約200字的短文介紹貓", "stream": False,
                               "options": {"num_predict": 400}})
    el = time.time() - t0
    row["load_s"] = round(d.get("load_duration", 0) / 1e9, 1)
    row["prompt_tps"] = round(d["prompt_eval_count"] / (d["prompt_eval_duration"] / 1e9), 1) if d.get("prompt_eval_count") else None
    n = d.get("eval_count", 0)
    row["gen_tok"] = n
    row["tps"] = round(n / (d["eval_duration"] / 1e9), 2) if d.get("eval_duration") else None
    row["total_s"] = round(el, 1)
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    try:
        post("/api/generate", {"model": name, "prompt": "hi", "keep_alive": 0})  # unload
    except Exception:
        pass
    time.sleep(3)
print("OLLAMA ALL DONE", flush=True)