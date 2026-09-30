# -*- coding: utf-8 -*-
# 統一殼層單測:python shelltest.py <殼名>
# 每次執行第0步固定卸載 Ollama 模型,確保 VRAM 只留 llama.cpp server (18910)
import json, time, subprocess, os, sys, urllib.request, threading

OUT = r"C:\Users\s92137\AppData\Local\Temp\claude\shell_results.json"
PROMPT = "用繁體中文寫一段約300字的文章介紹台灣夜市文化。直接開始內文,不要反問、不要前言。"
MODEL = "qwen3.8-27b-unc"
BASE = "http://127.0.0.1:18910"
NPM = r"C:\Users\s92137\AppData\Roaming\npm"

def cmd(c):
    return ["cmd", "/c", os.path.join(NPM, c + ".cmd")]

def unload_ollama():
    for m in ("qwen3.8-27b-unc-96k",):
        try:
            d = json.dumps({"model": m, "prompt": "hi", "keep_alive": 0}).encode()
            urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                   data=d, headers={"Content-Type": "application/json"}), timeout=600).read()
        except Exception:
            pass

def server_up():
    try:
        urllib.request.urlopen(BASE + "/health", timeout=3)
        return True
    except Exception:
        return False

TESTS = {
    "claude": (["claude", "-p", PROMPT, "--model", MODEL, "--effort", "medium", "--dangerously-skip-permissions"],
               {"ANTHROPIC_BASE_URL": BASE, "ANTHROPIC_API_KEY": "llamacpp",
                "ANTHROPIC_MODEL": MODEL, "ANTHROPIC_SMALL_FAST_MODEL": MODEL}),
    "opencode": (cmd("opencode") + ["run", PROMPT, "-m", "bench/qwen3.8-27b-unc"], None),
    "codex": (cmd("codex") + ["exec", PROMPT, "--skip-git-repo-check", "-m", MODEL,
                              "-c", 'model_provider="bench"',
                              "-c", 'model_providers.bench.name="llamacpp"',
                              "-c", 'model_providers.bench.base_url="' + BASE + '/v1"',
                              "-c", 'model_providers.bench.wire_api="responses"'], None),
    "qwen": (cmd("qwen") + ["-p", PROMPT, "-m", MODEL],
             {"OPENAI_BASE_URL": BASE + "/v1", "OPENAI_API_KEY": "llamacpp", "OPENAI_MODEL": MODEL}),
    "hermes": ([r"C:\Users\s92137\AppData\Local\hermes\bin\hermes.exe", "-z", PROMPT, "--yolo",
                "--provider", "llamacpp18910", "-m", "qwen3.8-27b-unc"], None),
    "cline": (["node", r"C:\Users\s92137\AppData\Roaming\npm\node_modules\cline\bin\cline",
               "-P", "openai-compatible", "-m", "qwen3.8-27b-unc", "--thinking", "medium"],
              {"OPENAI_BASE_URL": BASE + "/v1", "OPENAI_API_KEY": "llamacpp"},
              {"stdin": PROMPT}),
    "openclaw": (cmd("openclaw") + ["agent", "--agent", "main", "--session-id", "benchtest",
                                    "--message", PROMPT], None),
    "pi": (cmd("pi") + ["-p", PROMPT, "--provider", "llamacpp", "--model", "qwen3.8-27b-unc",
                        "--no-session", "--no-extensions", "--no-skills", "--no-prompt-templates"], None),
    "omp": ([r"C:\Users\s92137\AppData\Local\omp\omp.exe", "-p", PROMPT,
             "--model", "llamacpp/qwen3.8-27b-unc", "--no-session", "--no-lsp"], None),
}

def run(name, argv, env_extra, opts=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    stdin_text = (opts or {}).get("stdin")
    print(f"=== {name} 啟動…", flush=True)
    t0 = time.time()
    out_lines, chars = [], [0]
    try:
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", env=env,
                             stdin=subprocess.PIPE if stdin_text else subprocess.DEVNULL)
        if stdin_text:
            p.stdin.write(stdin_text + "\n")
            p.stdin.close()
        first = [None]
        def reader():
            for line in p.stdout:
                if first[0] is None and line.strip():
                    first[0] = time.time() - t0
                    print(f"  首字 {first[0]:.1f}s", flush=True)
                chars[0] += len(line)
                out_lines.append(line.rstrip())
            p.wait()
        th = threading.Thread(target=reader); th.start()
        while th.is_alive():
            th.join(timeout=10)
            if th.is_alive():
                print(f"  … {time.time()-t0:.0f}s ({chars[0]} 字元)", flush=True)
        row = {"shell": name, "ttft_s": round(first[0], 1) if first[0] else None,
               "total_s": round(time.time() - t0, 1), "returncode": p.returncode,
               "out_chars": chars[0], "out": "\n".join(out_lines)[-500:]}
        print(f"  完成 總{row['total_s']}s rc={row['returncode']}", flush=True)
    except Exception as e:
        row = {"shell": name, "error": repr(e)[:200]}
        print(f"  ❌ {row['error']}", flush=True)
    results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else []
    results = [r for r in results if r["shell"] != name]
    results.append(row)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: row.get(k) for k in ("shell", "total_s", "ttft_s", "returncode", "error")}, ensure_ascii=False), flush=True)

if __name__ == "__main__":
    name = sys.argv[1]
    if name not in TESTS:
        print("可測:", ", ".join(TESTS)); sys.exit(1)
    if not server_up():
        print("llama-server 18910 未啟動,先啟動它"); sys.exit(1)
    unload_ollama()
    print("Ollama 模型已卸載", flush=True)
    argv, env_extra = TESTS[name][:2]
    run(name, argv, env_extra, TESTS[name][2] if len(TESTS[name]) > 2 else None)