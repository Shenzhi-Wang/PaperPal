#!/usr/bin/env python3
"""
PaperPal - Main Entry Point

This is a simple entry point that calls the CLI implementation.
All functionality is implemented in cli.py.

Usage:
    python main.py [command] [options]
    # or equivalently:
    python cli.py [command] [options]

Commands:
    interactive (default)    Start interactive session
    search                   Quick search mode
    preferences              Manage preferences

Examples:
    # Interactive mode
    python main.py
    python main.py interactive
    
    # Search mode
    python main.py search -t "last week" -T "Large Language Models"
    python main.py search -t "today" -T "RAG" --mode exhaustive
    
    # Manage preferences
    python main.py preferences --show
    python main.py preferences --set-lang zh
    python main.py preferences --add-topic "Multimodal Learning"
    
    # Manage preference memory
    python main.py preferences --show-memory
    python main.py preferences --add-memory "I prefer practical papers"
    python main.py preferences --clear-memory
"""
from cli import main

if __name__ == "__main__":
    main()
