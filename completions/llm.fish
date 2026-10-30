# fish completion for llm / llm-ctl

for cmd in llm llm-ctl
    complete -c $cmd -f

    # Subcommands
    complete -c $cmd -n "__fish_use_subcommand" -a status -d "Show system, active model and hardware status"
    complete -c $cmd -n "__fish_use_subcommand" -a models -d "List all installed local models"
    complete -c $cmd -n "__fish_use_subcommand" -a ls -d "List all installed local models"
    complete -c $cmd -n "__fish_use_subcommand" -a switch -d "Switch active model and pre-warm into VRAM"
    complete -c $cmd -n "__fish_use_subcommand" -a use -d "Switch active model and sync clients"
    complete -c $cmd -n "__fish_use_subcommand" -a pull -d "Download model from Ollama registry"
    complete -c $cmd -n "__fish_use_subcommand" -a chat -d "Start interactive chat with model"
    complete -c $cmd -n "__fish_use_subcommand" -a start -d "Start local Ollama server"
    complete -c $cmd -n "__fish_use_subcommand" -a run -d "Start local Ollama server"
    complete -c $cmd -n "__fish_use_subcommand" -a stop -d "Stop local Ollama server gracefully"
    complete -c $cmd -n "__fish_use_subcommand" -a restart -d "Restart local Ollama server"
    complete -c $cmd -n "__fish_use_subcommand" -a unload -d "Unload model(s) from VRAM without deleting files"
    complete -c $cmd -n "__fish_use_subcommand" -a free -d "Evict all models to free 100% GPU VRAM"
    complete -c $cmd -n "__fish_use_subcommand" -a remove -d "Permanently delete model weights from disk"
    complete -c $cmd -n "__fish_use_subcommand" -a rm -d "Permanently delete model weights from disk"
    complete -c $cmd -n "__fish_use_subcommand" -a delete -d "Permanently delete model weights from disk"
    complete -c $cmd -n "__fish_use_subcommand" -a agents -d "Launch coding agent (claude, opencode, dsh)"
    complete -c $cmd -n "__fish_use_subcommand" -a doctor -d "Diagnose environment, drivers, agents, config"
    complete -c $cmd -n "__fish_use_subcommand" -a config -d "Inspect or edit configuration"
    complete -c $cmd -n "__fish_use_subcommand" -a help -d "Show help and command reference"

    # Aliases
    complete -c $cmd -n "__fish_use_subcommand" -a info -d "Show system, active model and hardware status"
    complete -c $cmd -n "__fish_use_subcommand" -a list -d "List all installed local models"
    complete -c $cmd -n "__fish_use_subcommand" -a launch -d "Launch coding agent (claude, opencode, dsh)"
    complete -c $cmd -n "__fish_use_subcommand" -a evict -d "Evict all models to free 100% GPU VRAM"

    # Global flags
    complete -c $cmd -l json -d "Output structured JSON"
    complete -c $cmd -s h -l help -d "Show help screen"

    # Positional argument completions
    complete -c $cmd -n "__fish_seen_subcommand_from switch use unload remove rm delete chat" -a "(ollama list 2>/dev/null | awk 'NR>1 {print \$1}')"
    complete -c $cmd -n "__fish_seen_subcommand_from agents launch" -a "claude opencode dsh"
    complete -c $cmd -n "__fish_seen_subcommand_from config" -a "show path set view"
end
