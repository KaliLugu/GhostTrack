function create_venv
    if test -d "venv"
        echo "'venv' already exist"
    else
        echo "venv creation..."
        python3 -m venv "venv"; or begin
            echo "❌ failed. python3 is installed ?"
            return 1
        end
        echo "✅ created"
    end
end

function activate_venv
    source venv/bin/activate.fish
    echo "✅ Venv activated ! ("(python3 --version)")"
end

create_venv; or return 1
activate_venv