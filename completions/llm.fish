# fish completion for llm / llm-ctl

complete -c llm -f
complete -c llm-ctl -f

# Subcommands
complete -c llm -n "__fish_use_subcommand" -a status -d "Show active model and hardware gauges"
complete -c llm -n "__fish_use_subcommand" -a ps -d "Display models currently occupying VRAM"
complete -c llm -n "__fish_use_subcommand" -a ls -d "List all installed models"
complete -c llm -n "__fish_use_subcommand" -a use -d "Hot-swap active model and sync clients"
complete -c llm -n "__fish_use_subcommand" -a free -d "Evict all models to free 100% GPU VRAM"
complete -c llm -n "__fish_use_subcommand" -a hub -d "Browse curated Ollama Model Hub"
complete -c llm -n "__fish_use_subcommand" -a pull -d "Download model from Ollama registry"
complete -c llm -n "__fish_use_subcommand" -a rm -d "Delete an installed model"
complete -c llm -n "__fish_use_subcommand" -a launch -d "Launch coding agent (claude, opencode, dsh)"
complete -c llm -n "__fish_use_subcommand" -a chat -d "Start direct terminal chat"
complete -c llm -n "__fish_use_subcommand" -a sync -d "Force sync configs across clients"
complete -c llm -n "__fish_use_subcommand" -a bench -d "View hardware tok/s benchmarks"
complete -c llm -n "__fish_use_subcommand" -a service -d "Control Ollama systemd service"

# Global flags
complete -c llm -l json -d "Output structured JSON"
complete -c llm -s h -l help -d "Show help screen"

# Second argument completions
complete -c llm -n "__fish_seen_subcommand_from use rm chat" -a "(ollama list 2>/dev/null | awk 'NR>1 {print \$1}')"
complete -c llm -n "__fish_seen_subcommand_from launch" -a "claude opencode dsh"
complete -c llm -n "__fish_seen_subcommand_from service" -a "start stop restart status logs"
