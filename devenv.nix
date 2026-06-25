{ pkgs, lib, config, inputs, ... }:

{
    packages = with pkgs; [
        stdenv.cc cmake ninja gnumake pkg-config
        vulkan-headers vulkan-loader vulkan-tools shaderc glslang
        
        gtk3
        gtk-layer-shell
        gobject-introspection

        qt6.qtsvg
        qt6.qtwayland
    ];

    languages.python = {
        enable = true;
        package = pkgs.python311.withPackages (ps: with ps; [ pygobject3 pyqt6 ]);
        venv.enable = false; 
    };

    env = {
        CMAKE_ARGS = "-DGGML_VULKAN=ON";
        CMAKE_EXECUTABLE = "${pkgs.cmake}/bin/cmake";
        NINJA_EXECUTABLE = "${pkgs.ninja}/bin/ninja";
        CC = "${pkgs.stdenv.cc}/bin/cc";
        CXX = "${pkgs.stdenv.cc}/bin/c++";

        LD_LIBRARY_PATH = lib.makeLibraryPath (with pkgs; [ 
            vulkan-loader 
            stdenv.cc.cc.lib 
        ]);

        GI_TYPELIB_PATH = lib.makeSearchPath "lib/girepository-1.0" (with pkgs; [
            gtk3
            gtk-layer-shell
            pango
            gdk-pixbuf
            atk
        ]);

        QT_PLUGIN_PATH = "${pkgs.qt6.qtsvg}/lib/qt-6/plugins:${pkgs.qt6.qtbase}/lib/qt-6/plugins";
    };

    enterShell = ''
        echo "🚀 Инициализация Native Wayland окружения..."

        if [ ! -d ".venv" ]; then
            python -m venv --system-site-packages .venv
        fi

        source .venv/bin/activate

        if ! python -c "import llama_cpp" &> /dev/null; then
            pip install llama-cpp-python --no-cache-dir
        fi
    '';
}
