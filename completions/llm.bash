# bash completion for llm / llm-ctl
_llm_completion() {
    local cur prev subcommands models agents
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    subcommands="status info ps top ls list models use switch free unload clear hub pull rm delete launch claude cc opencode oc dsh deepseek chat sync bench service help"
    agents="claude opencode dsh"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${subcommands} --json -h --help" -- "$cur") )
        return 0
    fi

    case "$prev" in
        use|switch|rm|delete|chat)
            models=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
            COMPREPLY=( $(compgen -W "${models}" -- "$cur") )
            return 0
            ;;
        launch)
            COMPREPLY=( $(compgen -W "${agents}" -- "$cur") )
            return 0
            ;;
        service)
            COMPREPLY=( $(compgen -W "start stop restart status logs" -- "$cur") )
            return 0
            ;;
    esac
}

complete -F _llm_completion llm
complete -F _llm_completion llm-ctl
