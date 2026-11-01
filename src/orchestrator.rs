use crate::App;
use serde_json::{json, Value};
use std::{
    env, fs,
    io::Write,
    path::{Path, PathBuf},
    time::Duration,
};

pub fn switch_model(app: &App, target: &str) -> Result<String, String> {
    if !app.reachable() {
        return Err("Ollama is offline. Run `llm start` first.".into());
    }
    let model = app
        .resolve(target)
        .ok_or_else(|| format!("No installed model matches '{target}'"))?;
    for loaded in app.loaded() {
        let name = if loaded.name.is_empty() {
            loaded.model
        } else {
            loaded.name
        };
        if name != model {
            let _ = app.stop_model(&name);
        }
    }
    app.save_active(&model)?;
    let warm = app
        .post(
            "/api/generate",
            &json!({"model":model,"prompt":"","stream":false}),
            Duration::from_secs(30),
        )
        .is_ok_and(|r| r.status().is_success());
    let synced = sync_agent_configs(app, &model);
    Ok(format!(
        "Active model: {model}{}{}",
        if warm {
            " (warmed)"
        } else {
            " (loads on first request)"
        },
        if synced.is_empty() {
            String::new()
        } else {
            format!("\n  Config sync: {}", synced.join(", "))
        }
    ))
}

pub fn write_config(path: &Path, mutate: impl FnOnce(&mut Value)) -> Result<(), String> {
    let mut value = if path.exists() {
        let bytes = fs::read(path).map_err(|e| e.to_string())?;
        serde_json::from_slice(&bytes).map_err(|e| {
            format!(
                "Refusing to replace invalid JSON in {}: {e}",
                path.display()
            )
        })?
    } else {
        json!({})
    };
    if !value.is_object() {
        return Err(format!(
            "Refusing to replace non-object JSON in {}",
            path.display()
        ));
    }
    mutate(&mut value);
    let tmp = path.with_extension(format!("tmp.{}", std::process::id()));
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let mut file = fs::File::create(&tmp).map_err(|e| e.to_string())?;
    file.write_all(&serde_json::to_vec_pretty(&value).map_err(|e| e.to_string())?)
        .and_then(|_| file.sync_all())
        .map_err(|e| e.to_string())?;
    fs::rename(tmp, path).map_err(|e| e.to_string())
}

pub fn sync_agent_configs(app: &App, model: &str) -> Vec<String> {
    let home = env::var_os("HOME").map(PathBuf::from).unwrap_or_default();
    let mut synced = Vec::new();
    let claude = home.join(".claude/settings.json");
    if write_config(&claude, |v| {
        v["model"] = json!(model);
        v["env"]["ANTHROPIC_BASE_URL"] = json!(app.host);
        v["env"]["ANTHROPIC_API_KEY"] = json!("ollama");
        for key in [
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
        ] {
            v["env"][key] = json!(model);
        }
    })
    .is_ok()
    {
        synced.push("Claude".into());
    }
    let opencode = env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .unwrap_or_else(|| home.join(".config"))
        .join("opencode/opencode.jsonc");
    if write_config(&opencode, |v| {
        v["$schema"] = json!("https://opencode.ai/config.json");
        v["model"] = json!(format!("ollama/{model}"));
    })
    .is_ok()
    {
        synced.push("OpenCode".into());
    }
    let pi = home.join(".pi/agent");
    let installed = app.models();
    if write_config(&pi.join("models.json"), |v| {
        v["$schema"] = json!("https://pi.dev/schemas/models.schema.json");
        v["providers"]["ollama"]["name"] = json!("Ollama (Local)");
        v["providers"]["ollama"]["baseUrl"] = json!("http://127.0.0.1:11434/v1");
        v["providers"]["ollama"]["api"] = json!("openai-completions");
        v["providers"]["ollama"]["apiKey"] = json!("ollama");
        if !v["providers"]["ollama"]["models"].is_array() {
            v["providers"]["ollama"]["models"] = json!([]);
        }
        let list = v["providers"]["ollama"]["models"].as_array_mut().unwrap();
        for name in std::iter::once(model.to_owned()).chain(installed.iter().map(|m| {
            if m.name.is_empty() {
                m.model.clone()
            } else {
                m.name.clone()
            }
        })) {
            if !list.iter().any(|entry| entry["id"] == name) {
                list.push(json!({"id":name,"name":format!("Ollama {name}")}));
            }
        }
    })
    .is_ok()
        && write_config(&pi.join("settings.json"), |v| {
            v["defaultProvider"] = json!("ollama");
            v["defaultModel"] = json!(model);
        })
        .is_ok()
    {
        synced.push("Pi".into());
    }
    let dsh = home.join(".dsh/profiles/web/cordis.patch.yml");
    if dsh.exists() {
        if let Ok(content) = fs::read_to_string(&dsh) {
            let mut lines: Vec<String> = content.lines().map(str::to_owned).collect();
            let mut in_block = false;
            let mut updated = false;
            for line in lines.iter_mut() {
                let trimmed = line.trim();
                if trimmed.starts_with("id:")
                    && (trimmed.contains("agent-default-model")
                        || trimmed.contains("\"agent-default-model\""))
                {
                    in_block = true;
                } else if in_block && trimmed.starts_with("id:") {
                    in_block = false;
                }
                if in_block && trimmed.starts_with("model:") {
                    let indent = line.len() - line.trim_start().len();
                    *line = format!("{:indent$}model: {}", "", model, indent = indent);
                    updated = true;
                    break;
                }
            }
            if updated {
                let tmp = dsh.with_extension(format!("tmp.{}", std::process::id()));
                if fs::write(&tmp, lines.join("\n") + "\n").is_ok() {
                    let _ = fs::rename(tmp, &dsh);
                    synced.push("DeepSeek Harness".into());
                }
            }
        }
    }
    synced
}
