create_venv() {
    if [ -d "venv" ]; then
        echo "'venv' already exist"
    else
        echo "venv creation..."
        python3 -m venv "venv" || {
            echo "❌ failed. python3 is installed ?"
            return 1
        }
        echo "✅ created"
    fi
}
 
activate_venv() {
    # need to start with source command
    if [ "${BASH_SOURCE[0]}" != "${0}" ] 2>/dev/null \
    || { [ -n "$ZSH_VERSION" ] && [[ "${(%):-%x}" != "$0" ]]; } 2>/dev/null; then
        source "venv/bin/activate"
        echo "✅ Venv activated ! ($(python3 --version))"
    else
        echo "⚠️ use : source mkvenv.sh"
    fi
}
 
create_venv || return 1
activate_venv
