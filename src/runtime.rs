use crate::{telemetry::command_exists, App};
use std::{
    process::{Command, Stdio},
    thread,
    time::Duration,
};

pub fn start(app: &App) -> Result<String, String> {
    if app.reachable() {
        return Ok(format!("Ollama is already active at {}", app.host));
    }
    if command_exists("systemctl") {
        let _ = Command::new("systemctl")
            .args(["--user", "start", "ollama"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        for _ in 0..12 {
            thread::sleep(Duration::from_millis(300));
            if app.reachable() {
                return Ok(format!(
                    "Started Ollama via systemd{}",
                    app.version()
                        .map(|v| format!(" (v{v})"))
                        .unwrap_or_default()
                ));
            }
        }
    }
    if !command_exists("ollama") {
        return Err("Ollama is unavailable: install it or ensure `ollama` is in PATH".into());
    }
    let child = Command::new("ollama")
        .arg("serve")
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed starting ollama serve: {e}"))?;
    std::mem::forget(child);
    for _ in 0..12 {
        thread::sleep(Duration::from_millis(300));
        if app.reachable() {
            return Ok("Started Ollama daemon".into());
        }
    }
    Err("Ollama process started but API did not become ready".into())
}

pub fn unload_all(app: &App) -> Vec<String> {
    app.loaded()
        .into_iter()
        .filter_map(|model| {
            let name = if model.name.is_empty() {
                model.model
            } else {
                model.name
            };
            if !name.is_empty() && app.stop_model(&name).is_ok() {
                Some(name)
            } else {
                None
            }
        })
        .collect()
}

pub fn stop(app: &App) -> Result<String, String> {
    if !app.reachable() {
        return Ok("Ollama is already stopped".into());
    }
    let _ = unload_all(app);
    if command_exists("systemctl") {
        let _ = Command::new("systemctl")
            .args(["--user", "stop", "ollama"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        for _ in 0..10 {
            thread::sleep(Duration::from_millis(200));
            if !app.reachable() {
                return Ok("Ollama stopped".into());
            }
        }
    }
    if command_exists("pkill") {
        let _ = Command::new("pkill")
            .args(["-f", "ollama serve"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        thread::sleep(Duration::from_millis(500));
    }
    if !app.reachable() {
        Ok("Ollama stopped".into())
    } else {
        Err("Could not stop Ollama. Check `systemctl --user status ollama`.".into())
    }
}

pub fn restart(app: &App) -> Result<String, String> {
    if command_exists("systemctl") {
        let _ = Command::new("systemctl")
            .args(["--user", "restart", "ollama"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status();
        for _ in 0..12 {
            thread::sleep(Duration::from_millis(300));
            if app.reachable() {
                return Ok(format!(
                    "Restarted Ollama via systemd{}",
                    app.version()
                        .map(|v| format!(" (v{v})"))
                        .unwrap_or_default()
                ));
            }
        }
    }
    stop(app)?;
    thread::sleep(Duration::from_millis(300));
    start(app)
}
