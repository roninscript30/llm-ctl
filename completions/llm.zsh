#compdef llm llm-ctl

_llm() {
    local -a commands agents config_actions
    commands=(
        'status:Show system, active model and hardware status'
        'models:List all installed local models'
        'ls:List all installed local models'
        'switch:Switch active model and pre-warm into VRAM'
        'use:Switch active model and sync clients'
        'pull:Download model from Ollama registry'
        'chat:Start direct terminal chat with model'
        'start:Start local Ollama server'
        'run:Start local Ollama server'
        'stop:Stop local Ollama server gracefully'
        'restart:Restart local Ollama server'
        'unload:Unload model(s) from VRAM without deleting files'
        'free:Evict all models to free 100% GPU VRAM'
        'remove:Permanently delete model weights from disk'
        'rm:Permanently delete model weights from disk'
        'delete:Permanently delete model weights from disk'
        'agents:Launch coding agent (claude, opencode, pi, dsh)'
        'pi:Launch Pi Coding Agent pre-wired to active model'
        'doctor:Diagnose environment, drivers, agents, config'
        'config:Inspect or edit configuration'
        'help:Show command reference and help screen'
        'info:Show system, active model and hardware status'
        'list:List all installed local models'
        'evict:Evict all models from VRAM'
        'launch:Launch coding agent (claude, opencode, dsh)'
    )

    agents=(
        'claude:Claude Code CLI'
        'opencode:OpenCode terminal agent'
        'pi:Pi Coding Agent CLI'
        'dsh:DeepSeek Harness Web/CLI'
    )

    config_actions=(
        'show:Show current configuration'
        'path:Print config file path'
        'set:Set configuration key value'
        'view:Show current configuration'
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
                switch|use|unload|remove|rm|delete|chat)
                    local -a installed_models
                    installed_models=(${(f)"$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')"})
                    _describe -t installed_models 'installed models' installed_models
                    ;;
                agents|launch)
                    _describe -t agents 'agent clients' agents
                    ;;
                config)
                    _describe -t config_actions 'config actions' config_actions
                    ;;
            esac
            ;;
    esac
}

compdef _llm llm llm-ctl 2>/dev/null || true
_llm "$@"
