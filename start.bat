@echo off
REM Simple Windows batch file to start Discord Social Analyzer
REM For advanced options, use start.ps1 instead

echo.
echo ========================================================
echo    Discord Social Analyzer - Simple Startup
echo ========================================================
echo.

REM Check for .env file
if not exist .env (
    echo [WARNING] .env file not found
    if exist .env.example (
        echo Copying .env.example to .env...
        copy .env.example .env >nul
        echo [SUCCESS] Created .env file
        echo.
        echo Please edit .env with your Discord token and settings
        echo Opening .env in notepad...
        start notepad .env
        echo.
        pause
    ) else (
        echo [ERROR] .env.example not found
        pause
        exit /b 1
    )
) else (
    echo [OK] .env file found
)

echo.
echo Starting Docker services...
docker compose up -d
if errorlevel 1 (
    echo [ERROR] Failed to start Docker services
    echo Make sure Docker Desktop is running
    pause
    exit /b 1
)

echo [SUCCESS] Docker services started
echo.
echo Waiting for services to initialize (10 seconds)...
timeout /t 10 /nobreak >nul

echo.
echo Starting Discord bot...
echo Press Ctrl+C to stop
echo.

REM Start the bot
python main.py

REM Cleanup on exit
echo.
echo Stopping Docker services...
docker compose down
echo [SUCCESS] Services stopped
echo.
pause
