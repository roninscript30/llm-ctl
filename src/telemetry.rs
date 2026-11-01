use serde_json::{json, Value};
use std::{fs, process::Command};

pub fn command_exists(bin: &str) -> bool {
    Command::new("sh")
        .args(["-c", "command -v \"$1\" >/dev/null 2>&1", "sh", bin])
        .status()
        .is_ok_and(|status| status.success())
}

pub fn mem() -> Value {
    let mut total = 0.0f64;
    let mut avail = 0.0f64;
    if let Ok(contents) = fs::read_to_string("/proc/meminfo") {
        for line in contents.lines() {
            let mut parts = line.split_whitespace();
            let key = parts.next().unwrap_or("");
            let value = parts
                .next()
                .and_then(|v| v.parse::<f64>().ok())
                .unwrap_or(0.0);
            match key {
                "MemTotal:" => total = value,
                "MemAvailable:" => avail = value,
                _ => {}
            }
        }
    }
    json!({
        "total_gb": (total / 1_048_576.0 * 100.0).round() / 100.0,
        "free_gb": (avail / 1_048_576.0 * 100.0).round() / 100.0,
        "used_gb": ((total - avail).max(0.0) / 1_048_576.0 * 100.0).round() / 100.0,
        "pct": if total > 0.0 { ((total - avail) / total * 1000.0).round() / 10.0 } else { 0.0 }
    })
}

pub fn parse_gpu_output(line: &str) -> Option<Value> {
    let parts: Vec<_> = line.split(',').map(str::trim).collect();
    if parts.len() < 6 {
        return None;
    }
    Some(json!({
        "name": parts[0],
        "used_mb": parts[1].parse::<f64>().unwrap_or(0.0),
        "total_mb": parts[2].parse::<f64>().unwrap_or(0.0),
        "util_pct": parts[3].parse::<f64>().unwrap_or(0.0),
        "temp_c": parts[4],
        "power_w": parts[5]
    }))
}

pub fn gpu() -> Option<Value> {
    if !command_exists("nvidia-smi") {
        return None;
    }
    let output = Command::new("nvidia-smi")
        .args([
            "--query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw",
            "--format=csv,noheader,nounits",
        ])
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let line = String::from_utf8_lossy(&output.stdout)
        .lines()
        .next()?
        .to_string();
    parse_gpu_output(&line)
}
