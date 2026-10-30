#compdef llm llm-ctl

_llm() {
    local -a commands agents service_actions
    commands=(
        'status:Show active model and hardware gauges'
        'ps:Display models currently occupying VRAM'
        'ls:List all installed models'
        'use:Hot-swap active model and sync clients'
        'free:Evict all models to free 100% GPU VRAM'
        'hub:Browse curated Ollama Model Hub with VRAM badges'
        'pull:Download model from Ollama registry'
        'rm:Delete an installed model'
        'launch:Launch coding agent (claude, opencode, dsh)'
        'chat:Start direct terminal chat'
        'sync:Force sync configs across clients'
        'bench:View hardware tok/s benchmarks'
        'service:Control Ollama systemd service'
        'help:Show help screen'
    )

    agents=(
        'claude:Claude Code CLI'
        'opencode:OpenCode terminal agent'
        'dsh:DeepSeek Harness Web/CLI'
    )

    service_actions=(
        'start:Start Ollama service'
        'stop:Stop Ollama service'
        'restart:Restart Ollama service'
        'status:Show service status'
        'logs:View service journal logs'
    )

    _arguments -C \
        '--json[Output structured JSON]' \
        '(-h --help)'{-h,--help}'[Show help message]' \
        '1: :->command' \
        '*:: :->args'

    case $state in
        command)
            _describe -t commands 'llm commands' commands
            ;;
        args)
            case $words[1] in
                use|switch|rm|delete|chat)
                    local -a installed_models
                    installed_models=(${(f)"$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')"})
                    _describe -t installed_models 'installed models' installed_models
                    ;;
                launch)
                    _describe -t agents 'agent clients' agents
                    ;;
                service)
                    _describe -t service_actions 'service actions' service_actions
                    ;;
            esac
            ;;
    esac
}

_llm "$@"
