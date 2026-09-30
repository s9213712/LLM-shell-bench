import json, time, subprocess, os, sys, urllib.request, threading

OUT = r"C:\Users\s92137\AppData\Local\Temp\claude\harness_results.json"
MODEL = "qwen3.8-27b-unc-96k"
PROMPT = "用繁體中文寫一段約300字的文章介紹台灣夜市文化。直接開始內文,不要反問、不要前言。"
OLLAMA = "http://127.0.0.1:11434"

def warm():
    d = json.dumps({"model": MODEL, "prompt": "hi", "stream": False}).encode()
    urllib.request.urlopen(urllib.request.Request(OLLAMA + "/api/generate", data=d,
                           headers={"Content-Type": "application/json"}), timeout=600).read()

def run(name, cmd, env_extra=None, timeout=1200):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    row = {"shell": name}
    t0 = time.time()
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", env=env, cwd=os.getcwd())
        first = [None]
        def reader():
            for line in p.stdout:
                if first[0] is None and line.strip():
                    first[0] = time.time() - t0
            p.wait()
        th = threading.Thread(target=reader); th.start()
        th.join(timeout)
        if th.is_alive():
            p.kill(); row["error"] = "TIMEOUT"
        row["ttft_s"] = round(first[0], 1) if first[0] else None   # startup + prompt processing
        row["total_s"] = round(time.time() - t0, 1)
        row["returncode"] = p.returncode
    except Exception as e:
        row["error"] = repr(e)[:200]
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    time.sleep(2)

results = []
if os.path.exists(OUT):
    results = json.load(open(OUT, encoding="utf-8"))
done = {r["shell"] for r in results if "error" not in r}

# fresh PATH entries (droid/omp installed after this session started)
reg = subprocess.run(["reg", "query", "HKCU\\Environment", "/v", "Path"], capture_output=True, text=True).stdout
user_path = [l.split("    ")[-1].strip() for l in reg.splitlines() if "REG_EXPAND_SZ" in l or "REG_SZ" in l]
path_dirs = os.environ["PATH"].split(os.pathsep) + (user_path[0].split(";") if user_path else [])
NEWPATH = os.pathsep.join(d for d in path_dirs if d)

CL = {"ANTHROPIC_BASE_URL": "http://127.0.0.1:11434", "ANTHROPIC_API_KEY": "ollama",
      "ANTHROPIC_MODEL": MODEL, "ANTHROPIC_SMALL_FAST_MODEL": MODEL}

def go(name, cmd, env_extra=None, timeout=1200):
    if name in done:
        return
    warm()
    run(name, cmd, env_extra, timeout)

go("Claude Code", ["claude", "-p", PROMPT, "--model", MODEL, "--dangerously-skip-permissions"], CL)
go("OpenCode", ["opencode", "run", PROMPT, "-m", f"ollama/{MODEL}"])
go("Codex CLI", ["codex", "exec", PROMPT, "--skip-git-repo-check",
                 "-m", MODEL, "-c", 'model_provider="ollama"',
                 "-c", 'model_providers.ollama.name="Ollama"',
                 "-c", 'model_providers.ollama.base_url="http://127.0.0.1:11434/v1"',
                 "-c", 'model_providers.ollama.wire_api="chat"'])
go("Qwen Code", ["qwen", "-p", PROMPT, "-m", MODEL],
   {"OPENAI_BASE_URL": "http://127.0.0.1:11434/v1", "OPENAI_API_KEY": "ollama", "OPENAI_MODEL": MODEL})
go("Hermes CLI", ["hermes", "-z", PROMPT, "--yolo"])
go("Cline", ["cline", PROMPT, "--auto-approve", "true"])
go("OpenClaw", ["openclaw", "agent", "--message", PROMPT])
go("Copilot CLI", ["copilot", "-p", PROMPT, "--allow-all-tools"],
   {"PATH": NEWPATH})
go("Droid", ["droid", "exec", PROMPT, "--auto", "low"],
   {"PATH": NEWPATH})
go("Oh My Pi", ["omp", "-p", PROMPT],
   {"PATH": NEWPATH})
go("DeepSeek Harness", ["dsh", "-p", PROMPT, "--yolo"],
   {"PATH": NEWPATH})
go("Pi", ["pi", "-p", PROMPT, "--provider", "google", "--model", "gemini-2.5-flash"])

# baseline: llama.cpp direct, full GPU + MTP, same prompt -> 100%
if "llama.cpp直跑" not in done:
    BIN = r"C:\Users\s92137\AppData\Local\hermes\runtimes\llamacpp\b10679\cuda"
    GGUF = r"E:\LLM\JonathanColetti\Qwen3.8-27B-Uncensored-GGUF\Qwen3.8-27B-Uncensored-Q4_K_M.gguf"
    proc = subprocess.Popen([BIN + r"\llama-server.exe", "--model", GGUF, "-c", "98304",
                             "-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on", "-ngl", "99",
                             "-b", "512", "-ub", "512", "--spec-type", "draft-mtp",
                             "--host", "127.0.0.1", "--port", "18910", "--no-warmup"],
                            cwd=BIN, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    BASE = "http://127.0.0.1:18910"
    up = False
    t0 = time.time()
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
               "prompt_tps": round(d.get("timings", {}).get("prompt_per_second", 0), 1),
               "gen_tok": d.get("usage", {}).get("completion_tokens", 0),
               "total_s": round(time.time() - t1, 1)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True)
print("HARNESS DONE", flush=True)