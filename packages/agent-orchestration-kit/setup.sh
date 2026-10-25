#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

# The user-level balanced profile is the default. Keep project mode explicit.
if [ "${1:-}" != --project ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        printf '%s\n' 'Python 3.11 or newer is required; no target files written.' >&2
        exit 1
    fi
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || {
        printf '%s\n' 'Python 3.11 or newer is required; no target files written.' >&2
        exit 1
    }
    export PYTHONDONTWRITEBYTECODE=1
    exec python3 "$script_dir/scripts/install_codex.py" "$@"
fi
shift
if [ "$#" -ne 0 ]; then
    printf '%s\n' 'Usage: ./setup.sh [user-install options] | ./setup.sh --project' >&2
    exit 1
fi

cat <<'BANNER'
+---------------------------------------+
|    ____   ___  ____  _____  __  __    |
|   / ___| / _ \|  _ \| ____| \ \/ /    |
|  | |    | | | | | | |  _|    \  /     |
|  | |___ | |_| | |_| | |___  /  \      |
|   \____| \___/|____/|_____|/_/\_\     |
|                                       |
|        O R C H E S T R A T O R        |
|    Orchestrate with Astra or Sol.     |
|          Execute with Luna.           |
+---------------------------------------+
BANNER
printf '%s\n' 'Interactive project setup'
printf '%s' 'Target repository path: '
IFS= read -r target_path || exit 1

if [ -z "$target_path" ] || [ ! -d "$target_path" ]; then
    printf 'Error: target must be an existing directory: %s\n' "${target_path:-<empty>}" >&2
    exit 1
fi

target_dir=$(CDPATH= cd -- "$target_path" && pwd -P)
if [ "$target_dir" = "$script_dir" ]; then
    printf 'Error: target repository must be different from the setup source directory.\n' >&2
    exit 1
fi

confirm() {
    prompt=$1
    default_yes=$2
    if [ "$default_yes" = yes ]; then
        suffix='[Y/n]'
    else
        suffix='[y/N]'
    fi

    while :; do
        printf '%s %s ' "$prompt" "$suffix"
        if ! IFS= read -r answer; then
            printf '\nSetup cancelled: input ended before setup was complete.\n' >&2
            exit 1
        fi

        case "$answer" in
            y|Y|yes|YES|Yes) return 0 ;;
            n|N|no|NO|No) return 1 ;;
            '') [ "$default_yes" = yes ] && return 0 || return 1 ;;
            *) printf '%s\n' 'Please answer yes or no.' ;;
        esac
    done
}

overwrite_paths() {
    source_path=$1
    destination_path=$2
    component_name=$(basename "$source_path")

    if [ -f "$source_path" ]; then
        if [ -e "$destination_path" ] || [ -L "$destination_path" ]; then
            printf '%s\n' "$component_name"
        else
            return
        fi
        return
    fi

    find "$source_path" -type f -print | while IFS= read -r source_file; do
        relative_path=${source_file#"$source_path"/}
        destination_file=$destination_path/$relative_path
        if [ -e "$destination_file" ] || [ -L "$destination_file" ]; then
            printf '%s\n' "$component_name/$relative_path"
        fi
    done
}

print_overwrites() {
    source_path=$1
    destination_path=$2

    overwrite_list=$(overwrite_paths "$source_path" "$destination_path")
    if [ -z "$overwrite_list" ]; then
        return
    fi

    printf '%s\n' 'WARNING: the following existing files will be overwritten:'
    printf '%s\n' "$overwrite_list" | sed 's/^/  - /'
}

merge_conflicts() {
    source_path=$1
    destination_path=$2

    find "$source_path" -type f -print | while IFS= read -r source_file; do
        relative_path=${source_file#"$source_path"/}
        destination_file=$destination_path/$relative_path
        if { [ -e "$destination_file" ] || [ -L "$destination_file" ]; } && [ ! -f "$destination_file" ]; then
            printf '%s\n' "$relative_path"
        fi
    done

    find "$source_path" -type d -print | while IFS= read -r source_directory; do
        if [ "$source_directory" = "$source_path" ]; then
            continue
        fi
        relative_path=${source_directory#"$source_path"/}
        destination_directory=$destination_path/$relative_path
        if { [ -e "$destination_directory" ] || [ -L "$destination_directory" ]; } && [ ! -d "$destination_directory" ]; then
            printf '%s\n' "$relative_path"
        fi
    done
}

select_plan() {
    printf '%s\n' 'Choose Profile to install'
    # Keep the original profiles first for existing numeric selections.
    printf '%s\n' '  1) Pro  - GPT-6 Astra (medium) orchestrates, GPT-6 Luna (max) executes, GPT-6 Astra (low) reviews'
    printf '%s\n' '  2) Plus - GPT-6 Luna (max) orchestrates, GPT-6 Luna (medium) executes, GPT-6 Astra (low) reviews'
    printf '%s\n' '  3) Pro (max 2 subagents) - GPT-6 Astra (medium) orchestrates, GPT-6 Luna (max) executes, GPT-6 Astra (low) reviews'
    printf '%s\n' '  4) Plus (max 2 subagents) - GPT-6 Luna (max) orchestrates, GPT-6 Luna (medium) executes, GPT-6 Astra (low) reviews'
    printf '%s\n' '  5) GPT6-SolMax-LunaMax - GPT-6.1 Sol (max) orchestrates and reviews, GPT-6 Luna (max) executes'
    printf '%s\n' '  6) GPT6-SolMedium-LunaMax - GPT-6.1 Sol (medium) orchestrates and reviews, GPT-6 Luna (max) executes'
    printf '%s\n' '  7) azhou-balanced - Sol high root/review, Luna max execution, optional Astra medium'

    while :; do
        printf '%s' 'Select Profile [1-7] (default 7): '
        if ! IFS= read -r answer; then
            printf '\nSetup cancelled: input ended before setup was complete.\n' >&2
            exit 1
        fi

        case "$answer" in
            1|pro|PRO|Pro) plan=pro; return ;;
            2|plus|PLUS|Plus) plan=plus; return ;;
            3|pro-max-2-subagents) plan=pro-max-2-subagents; return ;;
            4|plus-max-2-subagents) plan=plus-max-2-subagents; return ;;
            5|gpt6-SolMax-LunaMax|GPT6-SolMax-LunaMax) plan=GPT6-SolMax-LunaMax; return ;;
            6|gpt6-SolMedium-LunaMax|GPT6-SolMedium-LunaMax) plan=GPT6-SolMedium-LunaMax; return ;;
            7|azhou-balanced|'') plan=azhou-balanced; return ;;
            *) printf '%s\n' 'Please enter a listed profile number or name.' ;;
        esac
    done
}

copy_component() {
    name=$1
    source_path=${2:-$script_dir/$name}
    destination_path=$target_dir/$name
    component_installed=no

    if [ ! -e "$source_path" ]; then
        printf 'Error: setup source is missing: %s\n' "$source_path" >&2
        exit 1
    fi

    if [ -e "$destination_path" ] || [ -L "$destination_path" ]; then
        if [ "$name" = AGENTS.md ]; then
            if [ -L "$destination_path" ] || [ ! -f "$destination_path" ]; then
                printf 'Skipped %s: target must be a regular file, not a symbolic link.\n' "$name" >&2
                return 0
            fi
            instructions=$(cat "$source_path")
            existing_instructions=$(cat "$destination_path")
            case "$existing_instructions" in
                *"$instructions"*)
                    printf 'Skipped %s: instructions already present.\n' "$name"
                    return 0
                    ;;
            esac
            printf '\n\n' >> "$destination_path"
            cat "$source_path" >> "$destination_path"
            printf 'Appended instructions to %s. Existing contents preserved.\n' "$name"
            component_installed=yes
            return 0
        fi
        if [ ! -L "$destination_path" ] && [ -d "$source_path" ] && [ -d "$destination_path" ]; then
            linked_path=$(find "$destination_path" -type l -print -quit)
            if [ -n "$linked_path" ]; then
                printf 'Skipped %s: the existing target contains a symbolic link (%s).\n' \
                    "$name" "$linked_path" >&2
                return 0
            fi
            conflict_list=$(merge_conflicts "$source_path" "$destination_path")
            if [ -n "$conflict_list" ]; then
                printf 'Skipped %s: source and target types conflict at:\n' "$name" >&2
                printf '%s\n' "$conflict_list" | sed 's/^/  /' >&2
                return 0
            fi
        elif [ ! -L "$destination_path" ] && { [ -d "$source_path" ] && [ ! -d "$destination_path" ] || [ -f "$source_path" ] && [ ! -f "$destination_path" ]; }; then
            printf 'Skipped %s: source and target types are incompatible.\n' "$name" >&2
            return 0
        fi

        if [ -L "$destination_path" ]; then
            printf '%s\n' 'WARNING: the following symbolic link will be replaced:'
            printf '  - %s\n' "$name"
        else
            print_overwrites "$source_path" "$destination_path"
        fi
        if ! confirm "Update $name? New files will be added; only paths listed above will be replaced." no; then
            printf 'Skipped %s (existing target left unchanged).\n' "$name"
            return 0
        fi

        if [ -L "$destination_path" ]; then
            rm "$destination_path"
            cp -R "$source_path" "$destination_path"
        elif [ -d "$source_path" ] && [ -d "$destination_path" ]; then
            cp -R "$source_path"/. "$destination_path"/
        elif [ -f "$source_path" ] && [ -f "$destination_path" ]; then
            cp "$source_path" "$destination_path"
        fi
        printf 'Updated %s.\n' "$name"
    else
        cp -R "$source_path" "$destination_path"
        printf 'Installed %s.\n' "$name"
    fi
    component_installed=yes
}

plan=azhou-balanced
select_plan

installed=0
for component in .codex .agents AGENTS.md; do
    if confirm "Install $component?" yes; then
        if [ "$component" = .codex ]; then
            copy_component "$component" "$script_dir/profiles/$plan/codex"
        elif [ "$component" = .agents ]; then
            copy_component "$component" "$script_dir/profiles/$plan/agents"
        else
            copy_component "$component"
        fi
        if [ "$component_installed" = yes ]; then
            installed=$((installed + 1))
        fi
    else
        printf 'Skipped %s.\n' "$component"
    fi
done

printf '\nSetup complete. %s component(s) installed in %s (profile: %s).\n' "$installed" "$target_dir" "$plan"
printf '%s\n' 'See guides/ for optional Codex model and Fast-mode configurations.'
