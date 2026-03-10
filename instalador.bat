@echo off
setlocal enabledelayedexpansion

:: --- Configurações ---
set "VENV_DIR=venv"
set "APP_NAME=separador"
set "MAIN_FILE=main.py"
set "PYTHON_VERSION=3.12.10"

echo ====================================================
echo   Configurando Ambiente via Python Manager
echo ====================================================

:: 1. Verifica se o comando 'py' existe
where py >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo [ERRO] Comando 'py' nao encontrado. 
    echo Instale o Python Manager oficial da Microsoft Store.
    pause
    exit /b 1
)

echo [1/5] Verificando Python !PYTHON_VERSION!...

:: Tenta listar usando os tres formatos possiveis do oficial e do legado
set "INSTALADO=nao"

:: Teste 1: py list (Novo Manager)
py list 2>nul | findstr /C:"!PYTHON_VERSION!" >nul 2>&1
if !ERRORLEVEL! equ 0 set "INSTALADO=sim"

:: Teste 2: py --list (Variacao do Novo Manager)
if "!INSTALADO!"=="nao" (
    py --list 2>nul | findstr /C:"!PYTHON_VERSION!" >nul 2>&1
    if !ERRORLEVEL! equ 0 set "INSTALADO=sim"
)

:: Teste 3: py -0 (Launcher Antigo)
if "!INSTALADO!"=="nao" (
    py -0 2>nul | findstr /C:"!PYTHON_VERSION!" >nul 2>&1
    if !ERRORLEVEL! equ 0 set "INSTALADO=sim"
)

if "!INSTALADO!"=="sim" (
    echo [1/5] Python !PYTHON_VERSION! ja esta instalado.
) else (
    echo [1/5] Python !PYTHON_VERSION! nao encontrado. Instalando...
    echo Executando: py install !PYTHON_VERSION!
    
    py install !PYTHON_VERSION!
    
    if !ERRORLEVEL! neq 0 (
        echo.
        echo [ERRO] Falha na instalacao automatica.
        echo Se voce usa o Python Manager oficial, tente rodar no terminal:
        echo py install !PYTHON_VERSION!
        pause
        exit /b 1
    )
)

:: 2. Criacao da Venv
if not exist "!VENV_DIR!\Scripts\activate.bat" (
    echo [2/5] Criando ambiente virtual com Python !PYTHON_VERSION!...
    py -!PYTHON_VERSION! -m venv !VENV_DIR!
    
    if !ERRORLEVEL! neq 0 (
        echo [ERRO] Falha ao criar ambiente virtual com 'py -!PYTHON_VERSION!'.
        pause
        exit /b 1
    )
) else (
    echo [2/5] Ambiente virtual ja existe.
)

echo [3/5] Ativando ambiente e instalando dependencias...
call !VENV_DIR!\Scripts\activate.bat
python -m pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo [4/5] Compilando !APP_NAME!...
pyinstaller --noconsole --onefile --collect-all tensorflow --name "!APP_NAME!" "!MAIN_FILE!"

if exist "dist\!APP_NAME!.exe" (
    echo [5/5] Finalizando...
    move /y "dist\!APP_NAME!.exe" "." >nul
    if exist "build" rmdir /s /q "build"
    if exist "dist" rmdir /s /q "dist"
    if exist "!APP_NAME!.spec" del /q "!APP_NAME!.spec"
    echo ====================================================
    echo   SUCESSO !APP_NAME!.exe pronto na raiz.
    echo ====================================================
) else (
    echo [ERRO] Falha na compilacao. Verifique se o PyInstaller funcionou.
)

echo.
echo Pressione qualquer tecla para fechar...
pause >nul
