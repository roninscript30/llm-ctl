# bash completion for llm / llm-ctl
_llm_completion() {
    local cur prev subcommands models agents
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    subcommands="status info models ls list switch use pull chat start run stop restart unload free evict remove rm delete agents launch claude cc opencode oc dsh deepseek doctor config help"
    agents="claude opencode dsh"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "${subcommands} --json -h --help" -- "$cur") )
        return 0
    fi

    case "$prev" in
        switch|use|unload|remove|rm|delete|chat)
            models=$(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
            COMPREPLY=( $(compgen -W "${models}" -- "$cur") )
            return 0
            ;;
        agents|launch)
            COMPREPLY=( $(compgen -W "${agents}" -- "$cur") )
            return 0
            ;;
        config)
            COMPREPLY=( $(compgen -W "show path set view" -- "$cur") )
            return 0
            ;;
    esac
}

complete -F _llm_completion llm
complete -F _llm_completion llm-ctl
