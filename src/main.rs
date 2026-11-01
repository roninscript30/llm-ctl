use clap::{Parser, Subcommand};
use crossterm::{
    cursor,
    event::{self, Event, KeyCode, KeyEventKind, KeyModifiers},
    execute,
    terminal::{self, Clear, ClearType},
};
use reqwest::blocking::{Client, Response};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    env, fs,
    io::{self, IsTerminal, Read, Write},
    path::Path,
    process::{Command, Stdio},
    time::Duration,
};

mod orchestrator;
mod paths;
mod runtime;
mod telemetry;

use orchestrator::{switch_model, sync_agent_configs};
use paths::Paths;
use runtime::{restart as server_restart, start, stop as server_stop, unload_all};
use telemetry::{command_exists, gpu, mem};

const DEFAULT_MODEL: &str = "qwen2.5-coder:3b";

const LOGO: &str = "\x1b[1;96m  ██╗     ██╗     ███╗   ███╗               ██████╗ ████████╗ ██╗     \n  ██║     ██║     ████╗ ████║              ██╔════╝ ╚══██╔══╝ ██║     \n  ██║     ██║     ██╔████╔██║    ████████╗ ██║         ██║    ██║     \n  ██║     ██║     ██║╚██╔╝██║    ╚═══════╝ ██║         ██║    ██║     \n  ███████╗███████╗██║ ╚═╝ ██║              ╚██████╗    ██║    ███████╗\n  ╚══════╝╚══════╝╚═╝     ╚═╝               ╚═════╝    ╚═╝    ╚══════╝\x1b[0m\n          \x1b[2m───────────────────\x1b[0m \x1b[1;37mLOCAL MODEL CONTROL\x1b[0m \x1b[2m───────────────────\x1b[0m\n              \x1b[2mManage · Switch · Run · Integrate · Your Local Models\x1b[0m";

const QUICK_COMMANDS: &str = "Quick Commands:\n  models   List installed models        start    Start local server\n  switch   Switch active model          stop     Stop local server\n  chat     Start interactive chat       restart  Restart local server\n  pull     Download model from hub      status   Show system & model status\n  unload   Unload model from VRAM       doctor   Diagnose health & setup\n  remove   Remove model from disk       help     Show all commands";

#[derive(Parser, Debug, Clone)]
#[command(
    name = "llm",
    bin_name = "llm",
    version,
    about = "Local LLM lifecycle and Ollama controller",
    disable_help_subcommand = true
)]
pub struct Cli {
    /// Output response as JSON
    #[arg(long, global = true)]
    pub json: bool,

    #[command(subcommand)]
    pub command: Option<Cmd>,
}

#[derive(Subcommand, Debug, Clone)]
pub enum Cmd {
    /// Show runtime connectivity, hardware telemetry, and active model
    #[command(alias = "info")]
    Status {
        /// Output status telemetry as JSON
        #[arg(long)]
        json: bool,
    },
    /// List installed Ollama models with size, parameter count, and quantization
    #[command(alias = "ls", alias = "list")]
    Models {
        /// Output installed models list as JSON
        #[arg(long)]
        json: bool,
    },
    /// Switch the active model and synchronize coding agent configs
    #[command(alias = "use")]
    Switch {
        /// Model name or prefix to activate
        model: Option<String>,
    },
    /// Download a model from Ollama library with live progress
    Pull {
        /// Model tag to download (shows curated catalog if omitted)
        model: Option<String>,
    },
    /// Start interactive chat session with local model
    Chat {
        /// Model name to chat with (defaults to active model)
        model: Option<String>,
    },
    /// Unload model weights from GPU VRAM to reclaim memory
    #[command(alias = "free", alias = "evict")]
    Unload {
        /// Model name to evict (defaults to all loaded models)
        model: Option<String>,
    },
    /// Remove an installed model from local disk after confirmation
    #[command(alias = "rm", alias = "delete")]
    Remove {
        /// Model tag to remove
        model: String,
        /// Skip confirmation prompt
        #[arg(short = 'y', long)]
        yes: bool,
    },
    /// Start Ollama local background daemon
    #[command(alias = "run")]
    Start,
    /// Stop Ollama daemon gracefully
    Stop,
    /// Restart Ollama local daemon
    Restart,
    /// Launch or configure supported AI coding agents
    #[command(alias = "launch")]
    Agents {
        /// Agent name: claude, opencode, pi, or dsh
        name: Option<String>,
        /// Arguments forwarded directly to agent CLI
        #[arg(trailing_var_arg = true)]
        args: Vec<String>,
    },
    /// Launch Claude Code configured for local Ollama
    #[command(alias = "cc")]
    Claude {
        #[arg(trailing_var_arg = true)]
        args: Vec<String>,
    },
    /// Launch OpenCode interpreter routed to active Ollama model
    #[command(name = "opencode", alias = "open-code", alias = "oc")]
    OpenCode {
        #[arg(trailing_var_arg = true)]
        args: Vec<String>,
    },
    /// Launch Pi Coding Agent routed to active Ollama model
    Pi {
        #[arg(trailing_var_arg = true)]
        args: Vec<String>,
    },
    /// Launch DeepSeek Harness Web UI with Ollama profile
    #[command(alias = "deepseek")]
    Dsh {
        #[arg(trailing_var_arg = true)]
        args: Vec<String>,
    },
    /// Diagnose system health, Ollama connectivity, and agent dependencies
    Doctor,
    /// View and manage LLM-CTL configuration
    Config {
        #[arg(long)]
        json: bool,
        #[command(subcommand)]
        action: Option<ConfigCmd>,
    },
    /// Display command reference and help guide
    Help,
}

#[derive(Subcommand, Debug, Clone)]
pub enum ConfigCmd {
    /// Display current configuration JSON
    Show,
    /// Display path to configuration file
    Path,
    /// Update a configuration key
    Set {
        /// Config key (e.g. active_model, default_model)
        key: String,
        /// Value to assign
        value: String,
    },
}

#[derive(Serialize, Deserialize, Default)]
struct Config {
    #[serde(default)]
    active_model: Option<String>,
    #[serde(flatten)]
    rest: serde_json::Map<String, Value>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub(crate) struct Model {
    #[serde(default)]
    pub(crate) name: String,
    #[serde(default)]
    pub(crate) model: String,
    #[serde(default)]
    size: u64,
    #[serde(default)]
    size_vram: u64,
    #[serde(default)]
    details: Value,
    #[serde(default)]
    expires_at: String,
}

pub(crate) struct App {
    client: Client,
    pub(crate) host: String,
    paths: Paths,
}

impl App {
    pub(crate) fn new() -> Result<Self, String> {
        let paths = Paths::new();
        paths
            .ensure()
            .map_err(|e| format!("Cannot initialize user directories: {e}"))?;
        let host = env::var("OLLAMA_HOST")
            .unwrap_or_else(|_| "http://127.0.0.1:11434".into())
            .trim_end_matches('/')
            .to_string();
        let client = Client::builder()
            .timeout(Duration::from_secs(8))
            .build()
            .map_err(|e| e.to_string())?;
        Ok(Self {
            client,
            host,
            paths,
        })
    }

    fn request(&self, path: &str) -> Result<Response, reqwest::Error> {
        self.client.get(format!("{}{path}", self.host)).send()
    }

    pub(crate) fn post(
        &self,
        path: &str,
        body: &Value,
        timeout: Duration,
    ) -> Result<Response, reqwest::Error> {
        self.client
            .post(format!("{}{path}", self.host))
            .timeout(timeout)
            .json(body)
            .send()
    }

    pub(crate) fn reachable(&self) -> bool {
        self.request("/api/version")
            .is_ok_and(|r| r.status().is_success())
    }

    pub(crate) fn version(&self) -> Option<String> {
        self.request("/api/version")
            .ok()?
            .json::<Value>()
            .ok()?
            .get("version")?
            .as_str()
            .map(str::to_owned)
    }

    pub(crate) fn models(&self) -> Vec<Model> {
        self.request("/api/tags")
            .ok()
            .and_then(|r| r.json::<Value>().ok())
            .and_then(|v| serde_json::from_value(v.get("models")?.clone()).ok())
            .unwrap_or_default()
    }

    pub(crate) fn loaded(&self) -> Vec<Model> {
        self.request("/api/ps")
            .ok()
            .and_then(|r| r.json::<Value>().ok())
            .and_then(|v| serde_json::from_value(v.get("models")?.clone()).ok())
            .unwrap_or_default()
    }

    pub(crate) fn active(&self) -> String {
        fs::read(&self.paths.config)
            .ok()
            .and_then(|b| serde_json::from_slice::<Config>(&b).ok())
            .and_then(|c| c.active_model)
            .unwrap_or_else(|| DEFAULT_MODEL.into())
    }

    pub(crate) fn save_active(&self, name: &str) -> Result<(), String> {
        let mut c = if self.paths.config.exists() {
            let bytes = fs::read(&self.paths.config).map_err(|e| e.to_string())?;
            serde_json::from_slice::<Config>(&bytes).map_err(|e| {
                format!(
                    "Refusing to replace invalid config {}: {e}",
                    self.paths.config.display()
                )
            })?
        } else {
            Config::default()
        };
        c.active_model = Some(name.into());
        self.atomic_json(
            &self.paths.config,
            &serde_json::to_value(c).map_err(|e| e.to_string())?,
        )
    }

    fn atomic_json(&self, path: &Path, value: &Value) -> Result<(), String> {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        let tmp = path.with_extension(format!("tmp.{}", std::process::id()));
        let bytes = serde_json::to_vec_pretty(value).map_err(|e| e.to_string())?;
        let mut f = fs::File::create(&tmp).map_err(|e| e.to_string())?;
        f.write_all(&bytes)
            .and_then(|_| f.sync_all())
            .map_err(|e| e.to_string())?;
        fs::rename(tmp, path).map_err(|e| e.to_string())
    }

    pub(crate) fn resolve(&self, target: &str) -> Option<String> {
        let list = self.models();
        let names: Vec<_> = list
            .iter()
            .map(|m| {
                if m.name.is_empty() {
                    m.model.as_str()
                } else {
                    m.name.as_str()
                }
            })
            .filter(|n| !n.is_empty())
            .collect();
        let t = target.trim().to_lowercase();
        if let Ok(i) = t.parse::<usize>() {
            if (1..=names.len()).contains(&i) {
                return Some(names[i - 1].to_string());
            }
        }
        names
            .iter()
            .find(|n| n.to_lowercase() == t)
            .or_else(|| {
                names
                    .iter()
                    .find(|n| n.split(':').next().unwrap_or("").to_lowercase() == t)
            })
            .or_else(|| names.iter().find(|n| n.to_lowercase().starts_with(&t)))
            .or_else(|| names.iter().find(|n| n.to_lowercase().contains(&t)))
            .map(|n| n.to_string())
    }

    pub(crate) fn stop_model(&self, name: &str) -> Result<(), String> {
        if let Ok(r) = self.post(
            "/api/generate",
            &json!({"model":name,"keep_alive":0}),
            Duration::from_secs(8),
        ) {
            if r.status().is_success() {
                let _ = r.text();
                return Ok(());
            }
        }
        run_output("ollama", &["stop", name], Duration::from_secs(8)).map(|_| ())
    }
}

fn run_output(bin: &str, args: &[&str], timeout: Duration) -> Result<std::process::Output, String> {
    let mut child = Command::new(bin)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("{bin}: {e}"))?;
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| format!("Could not capture {bin} stdout"))?;
    let mut stderr = child
        .stderr
        .take()
        .ok_or_else(|| format!("Could not capture {bin} stderr"))?;
    let stdout_reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        let _ = stdout.read_to_end(&mut bytes);
        bytes
    });
    let stderr_reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        let _ = stderr.read_to_end(&mut bytes);
        bytes
    });
    let started = std::time::Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait().map_err(|e| format!("{bin}: {e}"))? {
            break status;
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!(
                "{bin} timed out after {} seconds",
                timeout.as_secs()
            ));
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    let o = std::process::Output {
        status,
        stdout: stdout_reader.join().unwrap_or_default(),
        stderr: stderr_reader.join().unwrap_or_default(),
    };
    if o.status.success() {
        Ok(o)
    } else {
        Err(String::from_utf8_lossy(&o.stderr).trim().to_string())
    }
}

fn launch_child(bin: &str, args: &[String], envs: &[(&str, &str)]) -> Result<(), String> {
    let mut c = Command::new(bin);
    c.args(args);
    for (k, v) in envs {
        c.env(k, v);
    }
    let status = c
        .status()
        .map_err(|e| format!("Cannot launch {bin}: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("{bin} exited with {status}"))
    }
}

fn print_models(app: &App, as_json: bool) {
    let list = app.models();
    let active = app.active();
    let loaded = app.loaded();
    if as_json {
        let out: Vec<_> = list
            .iter()
            .map(|m| {
                let n = if m.name.is_empty() {
                    &m.model
                } else {
                    &m.name
                };
                json!({
                    "name": n,
                    "size_bytes": m.size,
                    "details": m.details,
                    "is_active": n == &active,
                    "is_loaded": loaded.iter().any(|l| l.name == *n || l.model == *n),
                    "status": if loaded.iter().any(|l| l.name == *n || l.model == *n) { "IN_VRAM" } else { "STANDBY" }
                })
            })
            .collect();
        println!("{}", serde_json::to_string_pretty(&out).unwrap());
        return;
    }
    println!("\nInstalled models ({}):", list.len());
    if list.is_empty() {
        println!("  No models found. Start Ollama, then run `llm pull <model>`.\n");
        return;
    }
    for m in list {
        let n = if m.name.is_empty() { m.model } else { m.name };
        let marker = if loaded.iter().any(|l| l.name == n || l.model == n) {
            "● loaded"
        } else if n == active {
            "◈ active"
        } else {
            "· stored"
        };
        let details = &m.details;
        println!(
            "  {n:<30} {:>5.2} GiB  {}  {}  {marker}",
            m.size as f64 / 1_073_741_824.0,
            details
                .get("parameter_size")
                .and_then(Value::as_str)
                .unwrap_or("-"),
            details
                .get("quantization_level")
                .and_then(Value::as_str)
                .unwrap_or("-")
        );
    }
    println!();
}

fn ram_bar(pct: f64) -> String {
    let filled = ((pct / 100.0) * 8.0).round().clamp(0.0, 8.0) as usize;
    let empty = 8 - filled;
    format!("{}{}", "█".repeat(filled), "░".repeat(empty))
}

fn status(app: &App, as_json: bool) {
    let up = app.reachable();
    let loaded = app.loaded();
    let models = app.models();
    let g = gpu();
    let m = mem();
    let active = app.active();
    let is_loaded = loaded
        .iter()
        .any(|model| model.name == active || model.model == active);
    let is_installed = models
        .iter()
        .any(|model| model.name == active || model.model == active);
    let active_status = if is_loaded {
        "IN_VRAM"
    } else if is_installed {
        "STANDBY"
    } else {
        "NOT_INSTALLED"
    };
    let data = json!({
        "active_model": active,
        "active_model_status": active_status,
        "endpoint": app.host,
        "service_active": up,
        "version": if up { app.version() } else { None },
        "gpu": g.clone(),
        "system_ram": m.clone(),
        "loaded_models": loaded.clone(),
        "installed_models_count": models.len()
    });
    if as_json {
        println!("{}", serde_json::to_string_pretty(&data).unwrap());
        return;
    }
    println!("\n{}\n", LOGO);
    println!(
        "  ● Ollama: {} ({}{})  ❖ RAM: {:.1}/{:.1} GiB [{}] {:.0}%",
        if up { "Connected" } else { "Offline" },
        app.host,
        data["version"]
            .as_str()
            .map(|v| format!(" · v{v}"))
            .unwrap_or_default(),
        m["used_gb"].as_f64().unwrap_or(0.),
        m["total_gb"].as_f64().unwrap_or(0.),
        ram_bar(m["pct"].as_f64().unwrap_or(0.)),
        m["pct"].as_f64().unwrap_or(0.)
    );
    if let Some(ref g) = g {
        println!(
            "  ❖ GPU: {} · {:.0}% · {:.0}/{:.0} MiB       ❖ Model: {} [{}]",
            g["name"].as_str().unwrap_or("GPU"),
            g["util_pct"].as_f64().unwrap_or(0.),
            g["used_mb"].as_f64().unwrap_or(0.),
            g["total_mb"].as_f64().unwrap_or(0.),
            active,
            if is_loaded { "IN VRAM" } else { "READY" }
        );
    } else {
        println!(
            "  ❖ GPU: CPU Mode (No GPU detected)           ❖ Model: {} [{}]",
            active,
            if is_loaded { "IN VRAM" } else { "READY" }
        );
    }
    println!();
    println!("{QUICK_COMMANDS}\n");
}

struct HubModel {
    id: &'static str,
    params: &'static str,
    size_gb: f64,
    est_vram_mb: f64,
    desc: &'static str,
}

const HUB_MODELS: &[HubModel] = &[
    HubModel {
        id: "qwen2.5-coder:1.5b",
        params: "1.5B",
        size_gb: 0.98,
        est_vram_mb: 1400.0,
        desc: "Fast code completion & editing",
    },
    HubModel {
        id: "qwen2.5-coder:3b",
        params: "3.1B",
        size_gb: 1.90,
        est_vram_mb: 2600.0,
        desc: "Balanced local coding & tools",
    },
    HubModel {
        id: "deepseek-r1:1.5b",
        params: "1.8B",
        size_gb: 1.10,
        est_vram_mb: 1500.0,
        desc: "Fast reasoning & logic",
    },
    HubModel {
        id: "deepseek-r1:7b",
        params: "7.6B",
        size_gb: 4.70,
        est_vram_mb: 5200.0,
        desc: "Deep reasoning & architecture",
    },
    HubModel {
        id: "llama3.2:3b",
        params: "3.2B",
        size_gb: 2.00,
        est_vram_mb: 2800.0,
        desc: "General instruction following",
    },
    HubModel {
        id: "codellama:7b",
        params: "7.0B",
        size_gb: 3.80,
        est_vram_mb: 5000.0,
        desc: "Classic code specialization",
    },
];

fn print_hub_catalog() {
    let g = gpu();
    let total_vram = g
        .as_ref()
        .and_then(|val| val["total_mb"].as_f64())
        .unwrap_or(0.0);

    println!("\nCurated Model Hub:");
    println!(
        "  {:<22} {:<8} {:<10} {:<18} Description",
        "Model", "Params", "Disk", "Feasibility"
    );
    println!("  {}", "─".repeat(78));

    for m in HUB_MODELS {
        let badge = if total_vram > 0.0 {
            if m.est_vram_mb <= total_vram * 0.85 {
                "🟢 100% GPU"
            } else if m.est_vram_mb <= total_vram * 1.5 {
                "🟡 Hybrid"
            } else {
                "🔴 Heavy"
            }
        } else {
            "⚪ CPU Only"
        };
        println!(
            "  {:<22} {:<8} {:>5.2} GB   {:<18} {}",
            m.id, m.params, m.size_gb, badge, m.desc
        );
    }
    println!("\nUsage: llm pull <model>\n");
}

fn pull(app: &App, model: &str) -> Result<(), String> {
    let response = app
        .post(
            "/api/pull",
            &json!({"name":model,"stream":true}),
            Duration::from_secs(3600),
        )
        .map_err(|e| format!("Cannot connect to Ollama: {e}"))?;
    if !response.status().is_success() {
        return Err(format!("Ollama rejected pull: {}", response.status()));
    }
    let mut reader = io::BufReader::new(response);
    let mut line = String::new();
    loop {
        line.clear();
        let n = io::BufRead::read_line(&mut reader, &mut line).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        if let Ok(v) = serde_json::from_str::<Value>(&line) {
            let s = v["status"].as_str().unwrap_or("Downloading");
            let done = v["completed"].as_f64();
            let total = v["total"].as_f64();
            if let (Some(d), Some(t)) = (done, total) {
                if t > 0. {
                    print!("\r  {s}: {:>5.1}%", d / t * 100.);
                    let _ = io::stdout().flush();
                }
            } else {
                println!("  {s}");
            }
            if s == "success" {
                println!("\nPulled {model}");
                return Ok(());
            }
            if let Some(err) = v["error"].as_str() {
                return Err(err.into());
            }
        }
    }
    Ok(())
}

fn doctor(app: &App) {
    println!("\nLLM-CTL diagnostics");
    let up = app.reachable();
    println!("  {} Ollama at {}", if up { "✓" } else { "✗" }, app.host);
    if !up {
        println!("    Start with `llm start` or check that Ollama is installed.");
    }
    let ram = mem();
    println!(
        "  {} System RAM: {:.1}/{:.1} GiB ({:.1} GiB available)",
        if ram["free_gb"].as_f64().unwrap_or(0.) >= 1. {
            "✓"
        } else {
            "!"
        },
        ram["used_gb"].as_f64().unwrap_or(0.),
        ram["total_gb"].as_f64().unwrap_or(0.),
        ram["free_gb"].as_f64().unwrap_or(0.)
    );
    println!(
        "  {} NVIDIA telemetry",
        if gpu().is_some() {
            "✓ available"
        } else if command_exists("nvidia-smi") {
            "! query failed"
        } else {
            "○ unavailable (CPU mode)"
        }
    );
    let models = app.models();
    println!(
        "  {} Installed models: {}",
        if models.is_empty() { "!" } else { "✓" },
        models.len()
    );
    let active = app.active();
    println!(
        "  Active model: {active}{}",
        if models.iter().any(|m| m.name == active || m.model == active) {
            " (installed)"
        } else {
            " (not installed)"
        }
    );
    let cfg_ok = if app.paths.config.exists() {
        fs::read(&app.paths.config)
            .ok()
            .and_then(|b| serde_json::from_slice::<Value>(&b).ok())
            .is_some()
    } else {
        true
    };
    println!(
        "  {} Configuration at {}",
        if cfg_ok { "✓" } else { "✗" },
        app.paths.config.display()
    );
    for (name, binary) in [
        ("Claude Code", "claude"),
        ("OpenCode", "opencode"),
        ("Pi", "pi"),
        ("DeepSeek Harness", "dsh"),
    ] {
        println!(
            "  {} {name}: {}",
            if command_exists(binary) { "✓" } else { "○" },
            if command_exists(binary) {
                "available"
            } else {
                "not installed (optional)"
            }
        );
    }
    println!();
}

fn config(app: &App, action: Option<ConfigCmd>, as_json: bool) -> Result<(), String> {
    if as_json {
        let value = if app.paths.config.exists() {
            let bytes = fs::read(&app.paths.config).map_err(|e| e.to_string())?;
            serde_json::from_slice::<Value>(&bytes)
                .map_err(|e| format!("Invalid config JSON: {e}"))?
        } else {
            json!({"active_model": app.active()})
        };
        println!("{}", serde_json::to_string_pretty(&value).unwrap());
        return Ok(());
    }
    match action.unwrap_or(ConfigCmd::Show) {
        ConfigCmd::Show => {
            let val = fs::read_to_string(&app.paths.config)
                .unwrap_or_else(|_| format!("{{\n  \"active_model\": \"{}\"\n}}", app.active()));
            println!("{}\n{}", app.paths.config.display(), val);
        }
        ConfigCmd::Path => println!("{}", app.paths.config.display()),
        ConfigCmd::Set { key, value } => {
            if key != "active_model" {
                return Err(format!("Unknown config key: {key}"));
            }
            app.save_active(&value)?;
            let synced = sync_agent_configs(app, &value);
            println!(
                "Set active_model to {value}{}",
                if synced.is_empty() {
                    String::new()
                } else {
                    format!(" (synced {})", synced.join(", "))
                }
            );
        }
    }
    Ok(())
}

fn help() {
    println!("LLM-CTL · Local Model Control\n\nUsage: llm <command> [options]\n\nCommands:\n  status [--json]       Runtime and resource status\n  models [--json]       List installed models\n  switch <model>        Change active model and sync agent settings\n  pull [model]          Download a model through Ollama (or show hub)\n  chat [model]          Open Ollama chat\n  unload [model]        Release loaded model memory\n  remove <model> [-y]   Delete model weights from disk\n  start | stop | restart Manage Ollama server\n  agents [name] [args]  Launch claude, opencode, pi, or dsh\n  doctor                Diagnose runtime and local setup\n  config [show|path|set active_model <name>]\n  help                  Show this help\n\nRun `llm` without arguments for the interactive prompt.");
}

fn print_agents_menu(app: &App, prompt_user: bool) -> Result<Option<String>, String> {
    let active = app.active();
    let claude_ok = command_exists("claude");
    let opencode_ok = command_exists("opencode");
    let pi_ok = command_exists("pi");
    let dsh_ok = command_exists("dsh");

    println!("\nCoding Agent Integrations (Active Model: {active}):");
    println!(
        "  [1] Claude Code       (claude --model {active}) [{}]",
        if claude_ok { "Ready" } else { "Not Installed" }
    );
    println!(
        "  [2] OpenCode CLI      (opencode --model ollama/{active}) [{}]",
        if opencode_ok {
            "Ready"
        } else {
            "Not Installed"
        }
    );
    println!(
        "  [3] Pi Coding Agent   (pi --provider ollama --model {active}) [{}]",
        if pi_ok { "Ready" } else { "Not Installed" }
    );
    println!(
        "  [4] DeepSeek Harness  (dsh web on :3080) [{}]",
        if dsh_ok { "Ready" } else { "Not Installed" }
    );

    if prompt_user && io::stdin().is_terminal() {
        let choice = read_prompt("\nSelect agent [1-4, or Enter to cancel]: ")?;
        let selected = match choice.as_deref().map(str::trim) {
            Some("1") => Some("claude".into()),
            Some("2") => Some("opencode".into()),
            Some("3") => Some("pi".into()),
            Some("4") => Some("dsh".into()),
            _ => None,
        };
        Ok(selected)
    } else {
        println!("\nUsage: llm agents <claude|opencode|pi|dsh> [args...]\n");
        Ok(None)
    }
}

pub(crate) fn execute(app: &App, cmd: Cmd, global_json: bool) -> Result<bool, String> {
    match cmd {
        Cmd::Status { json } => status(app, json || global_json),
        Cmd::Models { json } => print_models(app, json || global_json),
        Cmd::Switch { model } => {
            let m = if let Some(m) = model {
                m
            } else if io::stdin().is_terminal() {
                print_models(app, false);
                let p = read_prompt("Model name: ")?;
                let Some(val) = p else {
                    return Ok(true);
                };
                val
            } else {
                return Err("Missing model name for switch. Usage: llm switch <model>".into());
            };
            println!("{}", switch_model(app, &m)?);
        }
        Cmd::Pull { model } => {
            if let Some(m) = model {
                pull(app, &m)?;
            } else {
                print_hub_catalog();
            }
        }
        Cmd::Chat { model } => {
            let m = model.unwrap_or_else(|| app.active());
            if !command_exists("ollama") {
                return Err("Ollama CLI is missing from PATH".into());
            }
            launch_child("ollama", &["run".into(), m], &[])?;
        }
        Cmd::Unload { model } => {
            if !app.reachable() {
                return Err("Ollama is offline".into());
            }
            if let Some(m) = model {
                let target = app.loaded().into_iter().find_map(|x| {
                    let n = if x.name.is_empty() { x.model } else { x.name };
                    if n == m || n.starts_with(&m) {
                        Some(n)
                    } else {
                        None
                    }
                });
                if let Some(n) = target {
                    app.stop_model(&n)?;
                    println!("Unloaded {n}");
                } else {
                    println!("{m} is not currently loaded");
                }
            } else {
                let names = unload_all(app);
                println!(
                    "Unloaded {} model(s){}",
                    names.len(),
                    if names.is_empty() {
                        String::new()
                    } else {
                        format!(": {}", names.join(", "))
                    }
                );
            }
        }
        Cmd::Remove { model, yes } => {
            if !yes {
                let ans = read_prompt(&format!(
                    "Permanently remove '{model}' and its weights? [y/N] "
                ))?;
                let confirmed = ans
                    .as_deref()
                    .is_some_and(|s| matches!(s.trim().to_lowercase().as_str(), "y" | "yes"));
                if !confirmed {
                    println!("Cancelled");
                    return Ok(true);
                }
            }
            if !command_exists("ollama") {
                return Err("Ollama executable not found in PATH".into());
            }
            if app.reachable() {
                let _ = app.stop_model(&model);
            }
            let out = run_output("ollama", &["rm", &model], Duration::from_secs(30))?;
            print!("{}", String::from_utf8_lossy(&out.stdout));
        }
        Cmd::Start => println!("{}", start(app)?),
        Cmd::Stop => println!("{}", server_stop(app)?),
        Cmd::Restart => println!("{}", server_restart(app)?),
        Cmd::Agents { name, args } => {
            let active = app.active();
            let agent_name = if let Some(n) = name {
                n
            } else {
                let choice = print_agents_menu(app, true)?;
                let Some(chosen) = choice else {
                    return Ok(true);
                };
                chosen
            };

            let (bin, mut all, envs): (String, Vec<String>, Vec<(&str, &str)>) =
                match agent_name.as_str() {
                    "claude" | "cc" => {
                        let envs = vec![
                            ("ANTHROPIC_BASE_URL", app.host.as_str()),
                            ("ANTHROPIC_API_KEY", "ollama"),
                            ("ANTHROPIC_DEFAULT_SONNET_MODEL", active.as_str()),
                            ("ANTHROPIC_DEFAULT_HAIKU_MODEL", active.as_str()),
                        ];
                        (
                            "claude".into(),
                            vec!["--model".into(), active.clone()],
                            envs,
                        )
                    }
                    "opencode" | "open-code" | "oc" => {
                        let _ = sync_agent_configs(app, &active);
                        (
                            "opencode".into(),
                            vec!["--model".into(), format!("ollama/{active}")],
                            vec![],
                        )
                    }
                    "pi" => {
                        let _ = sync_agent_configs(app, &active);
                        (
                            "pi".into(),
                            vec![
                                "--provider".into(),
                                "ollama".into(),
                                "--model".into(),
                                active.clone(),
                            ],
                            vec![],
                        )
                    }
                    "dsh" | "deepseek" => {
                        let _ = sync_agent_configs(app, &active);
                        let mut a = if args.is_empty()
                            || args.first().is_some_and(|x| x == "web" || x == "ui")
                        {
                            vec!["web".into()]
                        } else {
                            args.clone()
                        };
                        if a.is_empty() {
                            a.push("web".into());
                        }
                        ("dsh".into(), a, vec![])
                    }
                    _ => {
                        return Err(format!(
                            "Unknown agent '{agent_name}'. Choose claude, opencode, pi, or dsh."
                        ))
                    }
                };
            all.extend(args);
            if !command_exists(&bin) {
                return Err(format!("'{bin}' CLI is not found in PATH"));
            }
            launch_child(&bin, &all, &envs)?;
        }
        Cmd::Claude { args } => {
            execute(
                app,
                Cmd::Agents {
                    name: Some("claude".into()),
                    args,
                },
                global_json,
            )?;
        }
        Cmd::OpenCode { args } => {
            execute(
                app,
                Cmd::Agents {
                    name: Some("opencode".into()),
                    args,
                },
                global_json,
            )?;
        }
        Cmd::Pi { args } => {
            execute(
                app,
                Cmd::Agents {
                    name: Some("pi".into()),
                    args,
                },
                global_json,
            )?;
        }
        Cmd::Dsh { args } => {
            execute(
                app,
                Cmd::Agents {
                    name: Some("dsh".into()),
                    args,
                },
                global_json,
            )?;
        }
        Cmd::Doctor => doctor(app),
        Cmd::Config { action, json } => config(app, action, json || global_json)?,
        Cmd::Help => help(),
    }
    Ok(true)
}

fn read_prompt(label: &str) -> Result<Option<String>, String> {
    print!("{label}");
    io::stdout().flush().map_err(|e| e.to_string())?;
    let mut s = String::new();
    let bytes = io::stdin().read_line(&mut s).map_err(|e| e.to_string())?;
    if bytes == 0 {
        return Ok(None);
    }
    Ok(Some(s.trim().to_owned()))
}

fn parse_line_to_cmd(text: &str) -> Option<Cmd> {
    let mut parts = text.split_whitespace();
    let command = parts.next()?;
    let args: Vec<String> = parts.map(str::to_owned).collect();
    match command {
        "status" | "info" => Some(Cmd::Status { json: false }),
        "models" | "ls" | "list" => Some(Cmd::Models { json: false }),
        "switch" | "use" => Some(Cmd::Switch {
            model: args.first().cloned(),
        }),
        "pull" => Some(Cmd::Pull {
            model: args.first().cloned(),
        }),
        "chat" => Some(Cmd::Chat {
            model: args.first().cloned(),
        }),
        "unload" | "free" | "evict" => Some(Cmd::Unload {
            model: args.first().cloned(),
        }),
        "start" | "run" => Some(Cmd::Start),
        "stop" => Some(Cmd::Stop),
        "restart" => Some(Cmd::Restart),
        "doctor" => Some(Cmd::Doctor),
        "help" | "?" => Some(Cmd::Help),
        "agents" | "launch" => Some(Cmd::Agents {
            name: args.first().cloned(),
            args: args.iter().skip(1).cloned().collect(),
        }),
        "claude" | "cc" => Some(Cmd::Claude { args }),
        "opencode" | "open-code" | "oc" => Some(Cmd::OpenCode { args }),
        "pi" => Some(Cmd::Pi { args }),
        "dsh" | "deepseek" => Some(Cmd::Dsh { args }),
        "config" => Some(Cmd::Config {
            json: false,
            action: if args.first().is_some_and(|x| x == "path") {
                Some(ConfigCmd::Path)
            } else if args.first().is_some_and(|x| x == "set") && args.len() >= 3 {
                Some(ConfigCmd::Set {
                    key: args[1].clone(),
                    value: args[2].clone(),
                })
            } else {
                Some(ConfigCmd::Show)
            },
        }),
        _ => None,
    }
}

fn interactive(app: &App) -> Result<(), String> {
    let mut history: Vec<String> = fs::read_to_string(&app.paths.history)
        .unwrap_or_default()
        .lines()
        .map(str::to_owned)
        .collect();

    status(app, false);

    loop {
        let models: Vec<String> = app
            .models()
            .into_iter()
            .map(|m| if m.name.is_empty() { m.model } else { m.name })
            .collect();
        let line = read_line_editor(&mut history, &models)?;
        let Some(line) = line else {
            println!("\nBye.");
            break;
        };
        let text = line.trim();
        if text.is_empty() {
            continue;
        }
        if history.last().map(String::as_str) != Some(text) {
            history.push(text.into());
            if history.len() > 1000 {
                history.remove(0);
            }
        }
        let _ = fs::write(&app.paths.history, history.join("\n") + "\n");
        let mut parts = text.split_whitespace();
        let command = parts.next().unwrap_or("");
        if matches!(command, "exit" | "quit" | "q") {
            break;
        }
        if command == "clear" || command == "cls" {
            status(app, false);
            continue;
        }
        if let Some(c) = parse_line_to_cmd(text) {
            if let Err(e) = execute(app, c, false) {
                eprintln!("Error: {e}");
            }
        } else {
            println!("Unknown command '{command}'. Type `help`.");
        }
    }
    Ok(())
}

fn read_line_editor(history: &mut [String], models: &[String]) -> Result<Option<String>, String> {
    if !io::stdin().is_terminal() {
        let mut s = String::new();
        let bytes = io::stdin().read_line(&mut s).map_err(|e| e.to_string())?;
        if bytes == 0 {
            return Ok(None);
        }
        return Ok(Some(s.trim().to_owned()));
    }
    let mut stdout = io::stdout();
    let _ = terminal::enable_raw_mode();
    print!("\x1b[1;96mllm-ctl\x1b[0m \x1b[1;92m❯\x1b[0m ");
    stdout.flush().map_err(|e| e.to_string())?;
    let mut input = String::new();
    let mut hidx = history.len();

    let commands = [
        "status", "models", "switch", "pull", "chat", "unload", "remove", "start", "stop",
        "restart", "agents", "claude", "opencode", "pi", "dsh", "doctor", "config", "help",
        "clear", "exit", "quit",
    ];

    loop {
        if let Event::Key(k) = event::read().map_err(|e| e.to_string())? {
            if k.kind == KeyEventKind::Release {
                continue;
            }
            match k.code {
                KeyCode::Enter => {
                    println!();
                    terminal::disable_raw_mode().map_err(|e| e.to_string())?;
                    return Ok(Some(input));
                }
                KeyCode::Char('c') if k.modifiers.contains(KeyModifiers::CONTROL) => {
                    println!();
                    input.clear();
                    print!("\x1b[1;96mllm-ctl\x1b[0m \x1b[1;92m❯\x1b[0m ");
                    stdout.flush().ok();
                }
                KeyCode::Char('d') if k.modifiers.contains(KeyModifiers::CONTROL) => {
                    println!();
                    terminal::disable_raw_mode().ok();
                    return Ok(None);
                }
                KeyCode::Tab => {
                    let trimmed = input.trim_start();
                    if let Some(rest) = trimmed
                        .strip_prefix("switch ")
                        .or_else(|| trimmed.strip_prefix("use "))
                        .or_else(|| trimmed.strip_prefix("unload "))
                        .or_else(|| trimmed.strip_prefix("remove "))
                        .or_else(|| trimmed.strip_prefix("rm "))
                        .or_else(|| trimmed.strip_prefix("chat "))
                    {
                        let prefix = rest.trim();
                        let matches: Vec<_> =
                            models.iter().filter(|m| m.starts_with(prefix)).collect();
                        if matches.len() == 1 {
                            let cmd_prefix = trimmed.split_whitespace().next().unwrap_or("switch");
                            input = format!("{cmd_prefix} {}", matches[0]);
                            print!("\r\x1b[2K\x1b[1;96mllm-ctl\x1b[0m \x1b[1;92m❯\x1b[0m {input}");
                            stdout.flush().ok();
                        }
                    } else if !trimmed.is_empty() {
                        let matches: Vec<_> =
                            commands.iter().filter(|c| c.starts_with(trimmed)).collect();
                        if matches.len() == 1 {
                            input = format!("{} ", matches[0]);
                            print!("\r\x1b[2K\x1b[1;96mllm-ctl\x1b[0m \x1b[1;92m❯\x1b[0m {input}");
                            stdout.flush().ok();
                        }
                    }
                }
                KeyCode::Char(c) => {
                    input.push(c);
                    print!("{c}");
                    stdout.flush().ok();
                }
                KeyCode::Backspace => {
                    if input.pop().is_some() {
                        execute!(stdout, cursor::MoveLeft(1), Clear(ClearType::UntilNewLine)).ok();
                        stdout.flush().ok();
                    }
                }
                KeyCode::Up => {
                    if hidx > 0 {
                        hidx -= 1;
                        input = history[hidx].clone();
                        print!("\r\x1b[2K\x1b[1;96mllm-ctl\x1b[0m \x1b[1;92m❯\x1b[0m {input}");
                        stdout.flush().ok();
                    }
                }
                KeyCode::Down if hidx < history.len() => {
                    hidx += 1;
                    input = if hidx == history.len() {
                        String::new()
                    } else {
                        history[hidx].clone()
                    };
                    print!("\r\x1b[2K\x1b[1;96mllm-ctl\x1b[0m \x1b[1;92m❯\x1b[0m {input}");
                    stdout.flush().ok();
                }
                _ => {}
            }
        }
    }
}

fn main() {
    let result = (|| {
        let app = App::new()?;
        let cli = Cli::parse();
        if let Some(cmd) = cli.command {
            execute(&app, cmd, cli.json)?;
        } else if cli.json {
            status(&app, true);
        } else if !io::stdin().is_terminal() {
            let mut lines = Vec::new();
            let mut line = String::new();
            while let Ok(n) = io::stdin().read_line(&mut line) {
                if n == 0 {
                    break;
                }
                let trimmed = line.trim().to_string();
                if !trimmed.is_empty() {
                    lines.push(trimmed);
                }
                line.clear();
            }
            if lines.is_empty() {
                status(&app, false);
            } else {
                for l in lines {
                    if let Some(cmd) = parse_line_to_cmd(&l) {
                        execute(&app, cmd, false)?;
                    }
                }
            }
        } else {
            interactive(&app)?;
        }
        Ok::<(), String>(())
    })();
    if let Err(e) = result {
        eprintln!("Error: {e}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::telemetry::parse_gpu_output;

    #[test]
    fn command_aliases_parse() {
        assert!(matches!(
            Cli::try_parse_from(["llm", "ls"]).unwrap().command,
            Some(Cmd::Models { .. })
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "use", "model:tag"])
                .unwrap()
                .command,
            Some(Cmd::Switch { .. })
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "free"]).unwrap().command,
            Some(Cmd::Unload { .. })
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "opencode"]).unwrap().command,
            Some(Cmd::OpenCode { .. })
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "oc"]).unwrap().command,
            Some(Cmd::OpenCode { .. })
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "pi"]).unwrap().command,
            Some(Cmd::Pi { .. })
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "restart"]).unwrap().command,
            Some(Cmd::Restart)
        ));
        assert!(matches!(
            Cli::try_parse_from(["llm", "agents"]).unwrap().command,
            Some(Cmd::Agents { .. })
        ));
    }

    #[test]
    fn global_json_flag_parses() {
        let cli = Cli::try_parse_from(["llm", "--json"]).unwrap();
        assert!(cli.json);
        assert!(cli.command.is_none());

        let cli_status = Cli::try_parse_from(["llm", "--json", "status"]).unwrap();
        assert!(cli_status.json);
    }

    #[test]
    fn parse_line_to_cmd_supports_interactive_inputs() {
        assert!(matches!(
            parse_line_to_cmd("status"),
            Some(Cmd::Status { .. })
        ));
        assert!(matches!(
            parse_line_to_cmd("models"),
            Some(Cmd::Models { .. })
        ));
        assert!(matches!(
            parse_line_to_cmd("switch qwen2.5-coder:3b"),
            Some(Cmd::Switch { model: Some(_) })
        ));
        assert!(matches!(
            parse_line_to_cmd("unload"),
            Some(Cmd::Unload { model: None })
        ));
        assert!(matches!(parse_line_to_cmd("pi"), Some(Cmd::Pi { .. })));
        assert!(matches!(
            parse_line_to_cmd("opencode"),
            Some(Cmd::OpenCode { .. })
        ));
        assert!(matches!(parse_line_to_cmd("dsh"), Some(Cmd::Dsh { .. })));
        assert!(matches!(parse_line_to_cmd("restart"), Some(Cmd::Restart)));
        assert!(parse_line_to_cmd("unknown_cmd").is_none());
    }

    #[test]
    fn memory_report_has_nonnegative_values() {
        let report = mem();
        assert!(report["total_gb"].as_f64().unwrap_or(0.0) >= 0.0);
        assert!(report["free_gb"].as_f64().unwrap_or(0.0) >= 0.0);
        assert!(report["used_gb"].as_f64().unwrap_or(0.0) >= 0.0);
    }

    #[test]
    fn ram_bar_renders_eight_blocks() {
        let bar_0 = ram_bar(0.0);
        assert_eq!(bar_0.chars().count(), 8);
        assert_eq!(bar_0, "░░░░░░░░");

        let bar_50 = ram_bar(50.0);
        assert_eq!(bar_50.chars().count(), 8);
        assert_eq!(bar_50, "████░░░░");

        let bar_100 = ram_bar(100.0);
        assert_eq!(bar_100.chars().count(), 8);
        assert_eq!(bar_100, "████████");
    }

    #[test]
    fn gpu_output_parser() {
        let sample = "NVIDIA GeForce RTX 3050 Laptop GPU, 20, 4096, 5, 52, 14.50";
        let parsed = parse_gpu_output(sample).unwrap();
        assert_eq!(parsed["name"], "NVIDIA GeForce RTX 3050 Laptop GPU");
        assert_eq!(parsed["used_mb"], 20.0);
        assert_eq!(parsed["total_mb"], 4096.0);
        assert_eq!(parsed["util_pct"], 5.0);
        assert_eq!(parsed["temp_c"], "52");
        assert_eq!(parsed["power_w"], "14.50");

        assert!(parse_gpu_output("invalid,line").is_none());
    }

    #[test]
    fn config_updates_preserve_other_values_and_reject_invalid_json() {
        let path = env::temp_dir().join(format!("llm-ctl-config-test-{}.json", std::process::id()));
        fs::write(&path, r#"{"other":"kept","active_model":"old"}"#).unwrap();
        orchestrator::write_config(&path, |value| value["active_model"] = json!("new")).unwrap();
        let value: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(value["other"], "kept");
        assert_eq!(value["active_model"], "new");
        fs::write(&path, "not json").unwrap();
        assert!(orchestrator::write_config(&path, |_| {}).is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), "not json");
        fs::remove_file(path).unwrap();
    }

    #[test]
    fn paths_respect_xdg_env_vars() {
        let test_dir = env::temp_dir().join(format!("llm-paths-test-{}", std::process::id()));
        let cfg_dir = test_dir.join("config");
        let state_dir = test_dir.join("state");
        let cache_dir = test_dir.join("cache");

        let old_cfg = env::var_os("XDG_CONFIG_HOME");
        let old_state = env::var_os("XDG_STATE_HOME");
        let old_cache = env::var_os("XDG_CACHE_HOME");

        env::set_var("XDG_CONFIG_HOME", &cfg_dir);
        env::set_var("XDG_STATE_HOME", &state_dir);
        env::set_var("XDG_CACHE_HOME", &cache_dir);

        let paths = Paths::new();
        assert_eq!(paths.config_dir, cfg_dir.join("llm-ctl"));
        assert_eq!(paths.config, cfg_dir.join("llm-ctl/config.json"));
        assert_eq!(paths.history, state_dir.join("llm-ctl/history"));
        assert_eq!(paths.cache, cache_dir.join("llm-ctl"));

        assert!(paths.ensure().is_ok());
        assert!(paths.config_dir.exists());
        assert!(paths.state.join("logs").exists());

        // Restore env
        if let Some(val) = old_cfg {
            env::set_var("XDG_CONFIG_HOME", val);
        } else {
            env::remove_var("XDG_CONFIG_HOME");
        }
        if let Some(val) = old_state {
            env::set_var("XDG_STATE_HOME", val);
        } else {
            env::remove_var("XDG_STATE_HOME");
        }
        if let Some(val) = old_cache {
            env::set_var("XDG_CACHE_HOME", val);
        } else {
            env::remove_var("XDG_CACHE_HOME");
        }

        let _ = fs::remove_dir_all(test_dir);
    }
}
