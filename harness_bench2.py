import json, time, subprocess, os, urllib.request, threading

OUT = r"C:\Users\s92137\AppData\Local\Temp\claude\harness_results.json"
MODEL = "qwen3.8-27b-unc-96k"
PROMPT = "用繁體中文寫一段約300字的文章介紹台灣夜市文化。直接開始內文,不要反問、不要前言。"
OLLAMA = "http://127.0.0.1:11434"
NPM = r"C:\Users\s92137\AppData\Roaming\npm"

def cmd(c):  # npm .cmd shim needs cmd.exe
    return ["cmd", "/c", os.path.join(NPM, c + ".cmd")]

def warm():
    d = json.dumps({"model": MODEL, "prompt": "hi", "stream": False}).encode()
    urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate", data=d,
                           headers={"Content-Type": "application/json"}), timeout=600).read()

SHELLS = []  # (name, argv, env_extra) filled below; run() prints live progress

def run(name, argv, env_extra=None, timeout=1200, idx=0, total=0):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    print(f"\n=== [{idx}/{total}] {name} — 啟動中…", flush=True)
    row = {"shell": name}
    t0 = time.time()
    out_lines = []
    chars = [0]
    def reader():
        for line in p.stdout:
            if first[0] is None and line.strip():
                first[0] = time.time() - t0
                print(f"    首字輸出 {first[0]:.1f}s", flush=True)
            chars[0] += len(line)
            out_lines.append(line.rstrip())
        p.wait()
    try:
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", env=env)
        first = [None]
        th = threading.Thread(target=reader); th.start()
        while th.is_alive():
            th.join(timeout=5)
            if th.is_alive():
                print(f"    … {time.time()-t0:.0f}s 已輸出 {chars[0]} 字元", flush=True)
        if time.time() - t0 > timeout:
            p.kill(); row["error"] = "TIMEOUT"
        row["ttft_s"] = round(first[0], 1) if first[0] else None
        row["total_s"] = round(time.time() - t0, 1)
        row["returncode"] = p.returncode
        row["out_chars"] = chars[0]
        row["est_tok"] = round(chars[0] / 1.6)  # 中文~1.6字元/token 粗估
        row["est_tps"] = round(row["est_tok"] / row["total_s"], 1) if row["total_s"] else None
        row["out"] = "\n".join(out_lines)[-600:]
        if "error" not in row:
            print(f"    ✅ 完成 總{row['total_s']}s | 估算 ~{row['est_tps']} tok/s | rc={row['returncode']}", flush=True)
    except Exception as e:
        row["error"] = repr(e)[:200]
        print(f"    ❌ {row['error']}", flush=True)
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    time.sleep(2)

results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
done = {r["shell"] for r in results if "error" not in r and r.get("returncode") == 0}

CL = {"ANTHROPIC_BASE_URL": "http://127.0.0.1:11434", "ANTHROPIC_API_KEY": "ollama",
      "ANTHROPIC_MODEL": MODEL, "ANTHROPIC_SMALL_FAST_MODEL": MODEL}
NP = {"PATH": os.environ["PATH"] + os.pathsep + r"C:\Users\s92137\bin" + os.pathsep + r"C:\Users\s92137\AppData\Local\omp"}

SHELLS = [
    ("Claude Code", [r"C:\Users\s92137\.local\bin\claude.exe", "-p", PROMPT, "--model", MODEL, "--dangerously-skip-permissions"], CL),
    ("OpenCode", cmd("opencode") + ["run", PROMPT, "-m", f"ollama/{MODEL}"], None),
    ("Codex CLI", cmd("codex") + ["exec", PROMPT, "--skip-git-repo-check",
                                  "-m", MODEL, "-c", 'model_provider="ollama"',
                                  "-c", 'model_providers.ollama.name="Ollama"',
                                  "-c", 'model_providers.ollama.base_url="http://127.0.0.1:11434/v1"',
                                  "-c", 'model_providers.ollama.wire_api="chat"'], None),
    ("Qwen Code", cmd("qwen") + ["-p", PROMPT, "-m", MODEL],
     {"OPENAI_BASE_URL": "http://127.0.0.1:11434/v1", "OPENAI_API_KEY": "ollama", "OPENAI_MODEL": MODEL}),
    ("Hermes CLI", [r"C:\Users\s92137\AppData\Local\hermes\bin\hermes.exe", "-z", PROMPT, "--yolo"], None),
    ("Cline", cmd("cline") + [PROMPT, "--auto-approve", "true"], None),
    ("OpenClaw", cmd("openclaw") + ["agent", "--message", PROMPT], None),
    ("Copilot CLI", [r"C:\Users\s92137\AppData\Local\Microsoft\WinGet\Links\copilot.exe", "-p", PROMPT, "--allow-all-tools"], NP),
    ("Droid", [r"C:\Users\s92137\bin\droid.exe", "exec", PROMPT, "--auto", "low"], NP),
    ("Oh My Pi", [r"C:\Users\s92137\AppData\Local\omp\omp.exe", "-p", PROMPT], NP),
    ("DeepSeek Harness", cmd("dsh") + ["-p", PROMPT, "--yolo"], None),
    ("Pi", cmd("pi") + ["-p", PROMPT], None),
]
TOTAL = len(SHELLS) + 1
for i, (name, argv, env_extra) in enumerate(SHELLS, 1):
    if name in done:
        print(f"skip [{i}/{TOTAL}] {name} (已測成)", flush=True); continue
    warm()
    run(name, argv, env_extra, idx=i, total=TOTAL)

# baseline: unload ollama model first so llama-server gets full VRAM
try:
    d = json.dumps({"model": MODEL, "prompt": "hi", "keep_alive": 0}).encode()
    urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate", data=d,
                           headers={"Content-Type": "application/json"}), timeout=600).read()
except Exception:
    pass
time.sleep(3)
if "llama.cpp直跑" not in done:
    BIN = r"C:\Users\s92137\AppData\Local\hermes\runtimes\llamacpp\b10679\cuda"
    GGUF = r"E:\LLM\JonathanColetti\Qwen3.8-27B-Uncensored-GGUF\Qwen3.8-27B-Uncensored-Q4_K_M.gguf"
    proc = subprocess.Popen([BIN + r"\llama-server.exe", "--model", GGUF, "-c", "98304",
                             "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on", "-ngl", "99",
                             "-b", "512", "-ub", "512", "--spec-type", "draft-mtp",
                             "--host", "127.0.0.1", "--port", "18910", "--no-warmup"],
                            cwd=BIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    BASE = "http://127.0.0.1:18910"
    up, t0 = False, time.time()
    while time.time() - t0 < 600:
        if proc.poll() is not None:
            break
        try:
            urllib.request.urlopen(BASE + "/health", timeout=3); up = True; break
        except Exception:
            time.sleep(2)
    if up:
        t1 = time.time()
        d = json.loads(urllib.request.urlopen(urllib.request.Request(
            BASE + "/v1/chat/completions", data=json.dumps(
                {"messages": [{"role": "user", "content": PROMPT}], "max_tokens": 500}).encode(),
            headers={"Content-Type": "application/json"}), timeout=900).read())
        tim = d.get("timings", {})
        row = {"shell": "llama.cpp直跑", "tps": round(tim.get("predicted_per_second", 0), 2),
               "prompt_tps": round(tim.get("prompt_per_second", 0), 1),
               "gen_tok": d.get("usage", {}).get("completion_tokens", 0),
               "total_s": round(time.time() - t1, 1)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
print("HARNESS2 DONE", flush=True)