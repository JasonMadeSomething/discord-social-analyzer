#!/usr/bin/env python3
"""
Environment Configuration Checker
Validates your .env setup before running the bot.
"""

import sys
import os

def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_success(text):
    """Print success message."""
    print(f"✓ {text}")

def print_error(text):
    """Print error message."""
    print(f"✗ {text}")

def print_warning(text):
    """Print warning message."""
    print(f"⚠ {text}")

def check_env_file():
    """Check if .env file exists."""
    print_header("Checking .env file")
    if os.path.exists('.env'):
        print_success(".env file exists")
        return True
    else:
        print_error(".env file not found")
        print("  → Run: cp .env.example .env")
        return False

def check_imports():
    """Check if required packages are installed."""
    print_header("Checking Python packages")
    
    required_packages = [
        ('discord', 'discord.py'),
        ('sqlalchemy', 'sqlalchemy'),
        ('pydantic_settings', 'pydantic-settings'),
        ('faster_whisper', 'faster-whisper'),
        ('torch', 'torch'),
    ]
    
    all_installed = True
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print_success(f"{package_name} installed")
        except ImportError:
            print_error(f"{package_name} not installed")
            all_installed = False
    
    if not all_installed:
        print("\n  → Run: pip install -r requirements.txt")
    
    return all_installed

def check_config():
    """Check if configuration loads correctly."""
    print_header("Checking configuration")
    
    try:
        from src.config import settings
        print_success("Configuration loaded")
        return True, settings
    except Exception as e:
        print_error(f"Configuration failed to load: {e}")
        return False, None

def check_discord_token(settings):
    """Check Discord token."""
    print_header("Checking Discord token")
    
    if settings.discord_token and settings.discord_token != "your_bot_token_here":
        print_success("Discord token is set")
        print(f"  Token: {settings.discord_token[:20]}...")
        return True
    else:
        print_error("Discord token not configured")
        print("  → Set DISCORD_TOKEN in .env")
        return False

def check_database(settings):
    """Check database configuration."""
    print_header("Checking database")
    
    db_url = settings.get_database_url()
    
    # Check if URL is set
    if not db_url:
        print_error("Database URL not set")
        return False
    
    print_success("Database URL is configured")
    
    # Hide password in display
    if '@' in db_url:
        safe_url = db_url.split('@')[1]
        print(f"  Database: {safe_url}")
    
    # Try to connect
    try:
        from sqlalchemy import create_engine
        engine = create_engine(db_url, pool_pre_ping=True)
        conn = engine.connect()
        conn.close()
        print_success("Database connection successful")
        return True
    except Exception as e:
        print_error(f"Database connection failed: {e}")
        print("  → Ensure PostgreSQL is running")
        print("  → Check DATABASE_URL in .env")
        print("  → Verify database exists: psql -U postgres -l")
        return False

def check_whisper(settings):
    """Check Whisper configuration."""
    print_header("Checking Whisper configuration")
    
    print(f"  Model: {settings.whisper_model}")
    print(f"  Device: {settings.whisper_device}")
    print(f"  Compute type: {settings.whisper_compute_type}")
    
    # Check CUDA availability if using GPU
    if settings.whisper_device == "cuda":
        try:
            import torch
            if torch.cuda.is_available():
                print_success(f"CUDA is available")
                print(f"  GPU: {torch.cuda.get_device_name(0)}")
                return True
            else:
                print_warning("CUDA not available - GPU acceleration disabled")
                print("  → Check GPU drivers")
                print("  → Or set WHISPER_DEVICE=cpu in .env")
                return False
        except Exception as e:
            print_error(f"Could not check CUDA: {e}")
            return False
    else:
        print_warning("Using CPU for transcription (will be slow)")
        return True

def check_settings(settings):
    """Display other important settings."""
    print_header("Other settings")
    
    print(f"  Command prefix: {settings.command_prefix}")
    print(f"  Audio chunk duration: {settings.audio_chunk_duration}s")
    print(f"  Session timeout: {settings.session_timeout}s")
    print(f"  Log level: {settings.log_level}")
    
    # Check restrictions
    if settings.allowed_users:
        print_warning(f"Restricted to {len(settings.allowed_users)} allowed users")
    if settings.allowed_channels:
        print_warning(f"Restricted to {len(settings.allowed_channels)} allowed channels")
    if settings.admin_users:
        print(f"  Admin users: {len(settings.admin_users)}")

def main():
    """Main checker function."""
    print_header("Discord Social Analyzer - Configuration Checker")
    
    results = []
    
    # Check .env file
    results.append(check_env_file())
    
    # Check packages
    results.append(check_imports())
    
    # Try to load config
    config_ok, settings = check_config()
    results.append(config_ok)
    
    if not config_ok:
        print_header("Summary")
        print_error("Configuration check failed - fix errors above")
        sys.exit(1)
    
    # Check required settings
    results.append(check_discord_token(settings))
    results.append(check_database(settings))
    results.append(check_whisper(settings))
    
    # Show other settings
    check_settings(settings)
    
    # Summary
    print_header("Summary")
    
    if all(results):
        print_success("All checks passed! You're ready to run the bot.")
        print("\nTo start the bot:")
        print("  python main.py")
        sys.exit(0)
    else:
        print_error("Some checks failed - see errors above")
        print("\nCommon fixes:")
        print("  1. Copy example: cp .env.example .env")
        print("  2. Set Discord token in .env")
        print("  3. Install packages: pip install -r requirements.txt")
        print("  4. Start PostgreSQL and create database")
        print("\nFor detailed help, see:")
        print("  - SETUP.md (step-by-step setup)")
        print("  - CONFIG.md (configuration guide)")
        print("  - QUICK_CONFIG.md (ready-to-use configs)")
        sys.exit(1)

if __name__ == "__main__":
    main()
