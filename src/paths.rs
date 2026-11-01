use std::{env, fs, io, path::PathBuf};

#[derive(Clone)]
pub struct Paths {
    pub config_dir: PathBuf,
    pub config: PathBuf,
    pub state: PathBuf,
    pub history: PathBuf,
    pub cache: PathBuf,
}

impl Paths {
    pub fn new() -> Self {
        let home = env::var_os("HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| PathBuf::from("."));
        let cfg = env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".config"));
        let state = env::var_os("XDG_STATE_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".local/state"));
        let cache = env::var_os("XDG_CACHE_HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|| home.join(".cache"));
        let config_dir = cfg.join("llm-ctl");
        let state = state.join("llm-ctl");
        let cache = cache.join("llm-ctl");
        Self {
            config: config_dir.join("config.json"),
            history: state.join("history"),
            config_dir,
            state,
            cache,
        }
    }

    pub fn ensure(&self) -> io::Result<()> {
        for path in [
            &self.config_dir,
            &self.state,
            &self.cache,
            &self.state.join("logs"),
        ] {
            fs::create_dir_all(path)?;
        }
        let old = self.config_dir.join("history");
        if old.exists()
            && !self.history.exists()
            && fs::rename(&old, &self.history).is_err()
            && fs::copy(&old, &self.history).is_ok()
        {
            let _ = fs::remove_file(&old);
        }
        Ok(())
    }
}

impl Default for Paths {
    fn default() -> Self {
        Self::new()
    }
}
