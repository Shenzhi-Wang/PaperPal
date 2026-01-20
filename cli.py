#!/usr/bin/env python3
"""
PaperPal - Command Line Interface
Provides a friendly terminal interaction experience with auto-completion

This file contains all the core functionality. Can be run directly or via main.py.

Usage:
    python cli.py [command] [options]

Commands:
    interactive (default)    Interactive chat-like interface with command history
    search                   One-time search with specified parameters
    preferences              View and manage your research preferences

Key Features:
    - Natural language query parsing
    - Two search modes: keyword (fast) and exhaustive (thorough)
    - AI-powered paper scoring based on your interests
    - Auto-completion for commands (press Tab)
    - Command history (use ↑/↓ arrows)
    - Bilingual support (English/Chinese)
    - Automatic result export to Markdown files
"""
import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings


class LimitedFileHistory(FileHistory):
    """File history that limits the number of stored entries"""

    def append_string(self, string: str) -> None:
        super().append_string(string)
        try:
            # Read all lines and keep only the last 100
            with open(self.filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
            if len(lines) > 100:
                # Ensure directory exists before writing
                file_path = Path(self.filename)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.filename, "w", encoding="utf-8") as f:
                    # History entries in prompt_toolkit are prefixed with '+ '
                    # but FileHistory stores them line by line.
                    # Actually FileHistory just appends the string.
                    f.writelines(lines[-100:])
        except Exception:
            pass


from rich import print as rprint
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

import config
from src.arxiv_fetcher import ArxivFetcher
from src.interest_scorer import (
    InterestScorer,
    filter_papers_by_threshold,
    sort_papers_by_interest,
)
from src.llm_client import get_llm_client
from src.outputs_analyzer import get_outputs_analyzer
from src.paper import Paper
from src.preference_manager import PreferenceManager, get_preference_manager
from src.query_parser import ParsedQuery, QueryParser
from src.research_chat import ChatResponse, get_research_chat
from src.time_parser import TimeParser, parse_time_range
from src.topic_expander import get_topic_expander

console = Console()

# UI Translations
TRANSLATIONS = {
    "en": {
        "welcome_title": "PaperPal",
        "welcome_desc": "Discover AI papers from arXiv, scored by your interests.",
        "tips_title": "Tips for getting started",
        "tips_content": "Just describe what papers you want, e.g. 'LLM papers from last week'\n💡 Alt+Enter: New line | Enter: Submit",
        "shortcuts_hint": "? for shortcuts",
        "main_prompt": "› ",
        "ask_time_range": "[bold cyan]What time range?[/bold cyan] (e.g., 'last week', 'past 3 days', 'today')",
        "ask_topic": "[bold cyan]What topics interest you?[/bold cyan] (Press Enter to use saved preferences)",
        "time_range_display": "\n📅 Time Range: {start} to {end}",
        "topic_display": "🎯 Topic: {topic}",
        "using_saved_prefs": "📋 Using your saved preferences",
        "current_pref_title": "📋 Your Preferences",
        "current_pref_label": "[dim]Current Preferences:[/dim]",
        "fetching_papers": "Fetching papers from arXiv...",
        "fetched_papers_count": "\n✅ Fetched [bold green]{count}[/bold green] papers",
        "exhaustive_total_count": "\n📚 Total papers in date range: [bold green]{count}[/bold green] (before topic filtering)",
        "exhaustive_diag": "[dim]🔍 Diagnostic: API returned {raw} papers | {too_old} too old | {too_new} too new | Paper dates: {first_date} ~ {last_date}[/dim]",
        "title_filtering": "Coarse filtering by titles...",
        "title_filtered_count": "✅ Titles retained after coarse filter: [bold green]{count}[/bold green]",
        "search_mode": "Search Mode",
        "search_keywords": "Search keywords",
        "cleaned_topic": "Cleaned topic",
        "evaluating_papers": "Evaluating paper interest levels...",
        "parsing_query": "Parsing your request...",
        "no_papers_found": "[yellow]No papers found in the specified time range[/yellow]",
        "showing_papers_count": "\n📊 Showing [bold]{count}[/bold] papers (Threshold: {threshold})\n",
        "authors_label": "Authors",
        "categories_label": "Categories",
        "published_label": "Published",
        "abstract_label": "Abstract",
        "score_reason_label": "Scoring Reason",
        "link_label": "Link",
        "no_matching_papers": "\n[yellow]No matching papers found[/yellow]",
        "feedback_prompt": "\n[bold cyan]Any feedback?[/bold cyan] (e.g., 'Paper 1,3 not interesting' or Enter to skip)",
        "parsing_feedback": "Processing feedback...",
        "parsed_feedback_count": "\n✅ Recorded {count} feedback entries",
        "feedback_saved": "[green]✅ Preferences updated[/green]",
        "feedback_mode_entered": "[bold cyan]Entering feedback mode. Please describe your preferences:[/bold cyan]",
        "feedback_instruction": "[dim](e.g., 'I don't like RAG papers' or 'I prefer deep learning papers')[/dim]",
        "memory_compressed": "🗜️ Preference memory compressed",
        "memory_pruned": "🗑️ Old preferences removed to make room for new ones",
        "continue_prompt": "› ",
        "settings_prompt": "\n[dim]Type '/settings' to adjust preferences, language, or workers[/dim]",
        "exit_msg": "\n[dim]Goodbye! 👋[/dim]",
        "error_msg": "\n[red]Error: {error}[/red]",
        "network_error": "Network Error",
        "permission_error": "Permission Error",
        "general_error": "Error",
        "results_saved": "[green]✅ Results exported to: {path}[/green]",
        "export_title": "AI Paper Research Results",
        "export_date": "Date",
        "export_topic": "Topic",
        "export_count": "Count",
        "export_score": "Score",
        "export_arxiv_id": "ArXiv ID",
        "interrupt_msg": "\n\n[yellow]Goodbye![/yellow]",
        "lang_selection_prompt": "Choose language / 选择语言 (en/zh)",
        "first_time_save_prompt": "Should I remember your queries and feedback to improve recommendations?",
        "settings_menu": """
  [cyan]1[/] Language                   [dim]{lang}[/]
  [cyan]2[/] Search mode               [dim]{mode}[/]
  [cyan]3[/] Max workers               [dim]{workers}[/]
  [cyan]4[/] Save Interests & History    [dim]{save_status}[/]
  [cyan]5[/] Output directory           [dim]{output_dir}[/]
  [cyan]6[/] Save results               [dim]{save_results_status}[/]
  [cyan]7[/] Max display                [dim]{max_display}[/]
  [cyan]8[/] Auto-summary               [dim]{auto_summary_status}[/]
  [cyan]9[/] ArXiv Categories           [dim]{categories_count} selected[/]
  [cyan]10[/] Back
""",
        "select_option": "Select option (1-10)",
        "output_dir_updated": "[green]Output directory updated to: {path}[/green]",
        "save_results_toggled": "[green]Save results to file: {status}[/green]",
        "max_display_updated": "[green]Max display papers updated to: {count}[/green]",
        "enter_output_dir": "Enter output directory path",
        "enter_max_display": "Enter max display papers (or 'unlimited')",
        "workers_updated": "[green]Max workers updated to {count}[/green]",
        "save_toggled": "[green]Save interests & history: {status}[/green]",
        "invalid_option": "[yellow]Invalid option[/yellow]",
        "reset_msg": "[green]Conversation context reset[/green]",
        "search_mode_menu": """[dim]Current: {current}[/dim]

  [cyan]1[/] Keyword search    [dim]Fast, uses ArXiv keyword filtering[/]
  [cyan]2[/] Exhaustive search [dim]Thorough, downloads all papers[/]
""",
        "search_mode_updated": "[green]✅ Search mode set to: {mode}[/green]",
        "memory_menu": """
[dim]Your preference memory stores what the AI has learned about your interests.[/dim]

  [cyan]1[/] View current memory
  [cyan]2[/] Add to memory
  [cyan]3[/] Clear memory
  [cyan]4[/] Back
""",
        "memory_select_option": "Select option (1-4)",
        "memory_current_title": "📋 Current Preference Memory",
        "memory_empty": "[dim]Memory is empty. The AI will learn your preferences as you provide feedback.[/dim]",
        "memory_add_prompt": "Enter preference to add (e.g., 'I prefer practical ML papers over theoretical ones')",
        "memory_added": "[green]✅ Preference added to memory[/green]",
        "memory_cleared": "[green]✅ Preference memory cleared[/green]",
        "memory_clear_confirm": "Are you sure you want to clear all preference memory?",
        # Chat mode
        "chat_mode_title": "💬 Research Chat Mode",
        "chat_mode_desc": "Discuss papers, analyze trends, find connections.\nTips: Alt+Enter for new line, Enter to submit, '/exit' to leave.",
        "chat_prompt": "chat › ",
        "chat_processing": "Thinking...",
        "chat_write_confirm": "Save this response to file?",
        "chat_saved": "[green]✅ Response saved to: {path}[/green]",
        "chat_search_suggest": "[cyan]💡 Suggested search:[/cyan] {query}",
        "chat_no_files": "[yellow]No result files found. Search for papers first.[/yellow]",
        "chat_exit": "[dim]Exiting chat mode[/dim]",
        "verifying_query": "Understanding your request...",
        # Files
        "files_title": "📁 Result Files",
        "files_empty": "[yellow]No result files found in outputs directory.[/yellow]",
        "files_select_prompt": "Enter file number to view (or Enter to skip)",
        # Summary
        "summary_generating": "Generating summary...",
        "summary_title": "📋 Research Summary",
        "summary_added": "[green]✅ Summary added to: {path}[/green]",
        "summary_no_papers": "[yellow]No papers to summarize.[/yellow]",
        "auto_summary_toggled": "[green]Auto-summary: {status}[/green]",
        "arxiv_categories_label": "ArXiv Categories",
        "arxiv_categories_updated": "[green]ArXiv categories updated[/green]",
        "output_path_label": "Output Path",
        "categories_instruction": "[bold cyan]↑/↓[/] to move, [bold cyan]Enter[/] to toggle, [bold cyan]s[/] to save & exit, [bold cyan]q[/] to cancel",
        "select_categories_prompt": "Select categories (enter numbers separated by space/comma to toggle, 'all' for all, 'none' for none, or Enter when done)",
    },
    "zh": {
        "welcome_title": "PaperPal",
        "welcome_desc": "从 arXiv 发现 AI 论文，根据您的兴趣智能评分。",
        "tips_title": "快速开始",
        "tips_content": "直接描述您想找的论文，如 '最近一周的大模型论文'\n💡 Alt+Enter: 换行 | Enter: 提交",
        "shortcuts_hint": "? 查看快捷命令",
        "main_prompt": "› ",
        "ask_time_range": "[bold cyan]时间范围？[/bold cyan] (如 '最近一周', '过去三天', '今天')",
        "ask_topic": "[bold cyan]您对什么主题感兴趣？[/bold cyan] (回车使用已保存的偏好)",
        "time_range_display": "\n📅 时间范围: {start} 到 {end}",
        "topic_display": "🎯 主题: {topic}",
        "using_saved_prefs": "📋 使用您保存的偏好",
        "current_pref_title": "📋 您的偏好",
        "current_pref_label": "[dim]当前偏好设置：[/dim]",
        "fetching_papers": "正在从 arXiv 获取论文...",
        "fetched_papers_count": "\n✅ 获取到 [bold green]{count}[/bold green] 篇论文",
        "exhaustive_total_count": "\n📚 该时间范围内共 [bold green]{count}[/bold green] 篇论文（主题过滤前）",
        "exhaustive_diag": "[dim]🔍 诊断信息: API 返回 {raw} 篇 | {too_old} 篇太旧 | {too_new} 篇太新 | 论文日期范围: {first_date} ~ {last_date}[/dim]",
        "title_filtering": "正在根据标题进行粗筛...",
        "title_filtered_count": "✅ 粗筛后保留 [bold green]{count}[/bold green] 篇论文",
        "search_mode": "搜索模式",
        "search_keywords": "搜索关键词",
        "cleaned_topic": "清理后主题",
        "evaluating_papers": "正在评估论文兴趣度...",
        "parsing_query": "正在处理您的请求...",
        "no_papers_found": "[yellow]在指定时间范围内没有找到论文[/yellow]",
        "showing_papers_count": "\n📊 显示 [bold]{count}[/bold] 篇论文 (阈值: {threshold}分)\n",
        "authors_label": "作者",
        "categories_label": "类别",
        "published_label": "发布",
        "abstract_label": "摘要",
        "score_reason_label": "评分原因",
        "link_label": "链接",
        "no_matching_papers": "\n[yellow]没有找到符合条件的论文[/yellow]",
        "feedback_prompt": "\n[bold cyan]有反馈吗？[/bold cyan] (如 '第1、3篇不感兴趣' 或回车跳过)",
        "parsing_feedback": "正在处理反馈...",
        "parsed_feedback_count": "\n✅ 记录了 {count} 条反馈",
        "feedback_saved": "[green]✅ 偏好已更新[/green]",
        "feedback_mode_entered": "[bold cyan]进入反馈模式。请描述您的偏好：[/bold cyan]",
        "feedback_instruction": "[dim](例如：'我不喜欢 RAG 论文' 或 '我更喜欢深度学习方面的论文')[/dim]",
        "memory_compressed": "🗜️ 偏好记忆已压缩",
        "memory_pruned": "🗑️ 已删除旧偏好以腾出空间",
        "continue_prompt": "› ",
        "settings_prompt": "\n[dim]输入 '/settings' 调整偏好、语言或线程数[/dim]",
        "exit_msg": "\n[dim]再见！👋[/dim]",
        "error_msg": "\n[red]错误: {error}[/red]",
        "network_error": "网络错误",
        "permission_error": "权限错误",
        "general_error": "错误",
        "results_saved": "[green]✅ 结果已导出至: {path}[/green]",
        "output_path_label": "输出路径",
        "export_title": "AI 论文研究结果",
        "export_date": "日期",
        "export_topic": "主题",
        "export_count": "数量",
        "export_score": "评分",
        "export_arxiv_id": "ArXiv ID",
        "interrupt_msg": "\n\n[yellow]再见！[/yellow]",
        "lang_selection_prompt": "选择语言 / Choose language (en/zh)",
        "first_time_save_prompt": "是否记住您的查询和反馈以改进推荐？",
        "settings_menu": """
  [cyan]1[/] 语言                        [dim]{lang}[/]
  [cyan]2[/] 搜索模式                    [dim]{mode}[/]
  [cyan]3[/] 最大线程数                  [dim]{workers}[/]
  [cyan]4[/] 保存用户兴趣和搜索历史      [dim]{save_status}[/]
  [cyan]5[/] 输出目录                    [dim]{output_dir}[/]
  [cyan]6[/] 保存结果                    [dim]{save_results_status}[/]
  [cyan]7[/] 最大显示数                  [dim]{max_display}[/]
  [cyan]8[/] 自动生成摘要                [dim]{auto_summary_status}[/]
  [cyan]9[/] ArXiv 搜索类别              [dim]已选择 {categories_count} 个[/]
  [cyan]10[/] 返回
""",
        "select_option": "选择选项 (1-10)",
        "output_dir_updated": "[green]输出目录已更新为: {path}[/green]",
        "save_results_toggled": "[green]保存结果到文件: {status}[/green]",
        "max_display_updated": "[green]最大显示论文数已更新为: {count}[/green]",
        "enter_output_dir": "输入输出目录路径",
        "enter_max_display": "输入最大显示论文数 (或输入 'unlimited' 表示不限制)",
        "workers_updated": "[green]最大线程数已更新为 {count}[/green]",
        "save_toggled": "[green]保存用户兴趣和搜索历史: {status}[/green]",
        "invalid_option": "[yellow]无效选项[/yellow]",
        "reset_msg": "[green]对话上下文已重置[/green]",
        "search_mode_menu": """[dim]当前: {current}[/dim]

  [cyan]1[/] 关键词搜索    [dim]快速，使用 ArXiv 关键词过滤[/]
  [cyan]2[/] 遍历搜索      [dim]全面，下载所有论文后评分[/]
""",
        "search_mode_updated": "[green]✅ 搜索模式已设置为: {mode}[/green]",
        "memory_menu": """
[dim]偏好记忆存储了 AI 从您的反馈中学习到的兴趣偏好。[/dim]

  [cyan]1[/] 查看当前记忆
  [cyan]2[/] 添加偏好
  [cyan]3[/] 清空记忆
  [cyan]4[/] 返回
""",
        "memory_select_option": "选择选项 (1-4)",
        "memory_current_title": "📋 当前偏好记忆",
        "memory_empty": "[dim]记忆为空。AI 会在您提供反馈时学习您的偏好。[/dim]",
        "memory_add_prompt": "输入要添加的偏好 (如 '我更喜欢实用的机器学习论文而非理论性的')",
        "memory_added": "[green]✅ 偏好已添加到记忆[/green]",
        "memory_cleared": "[green]✅ 偏好记忆已清空[/green]",
        "memory_clear_confirm": "确定要清空所有偏好记忆吗？",
        # Chat mode
        "chat_mode_title": "💬 研究对话模式",
        "chat_mode_desc": "讨论论文、分析趋势、发现联系。\n提示：Alt+Enter 换行，Enter 提交，'/exit' 退出。",
        "chat_prompt": "对话 › ",
        "chat_processing": "正在思考...",
        "chat_write_confirm": "是否保存此回复到文件？",
        "chat_saved": "[green]✅ 回复已保存至: {path}[/green]",
        "chat_search_suggest": "[cyan]💡 建议搜索:[/cyan] {query}",
        "chat_no_files": "[yellow]未找到结果文件。请先搜索论文。[/yellow]",
        "chat_exit": "[dim]退出对话模式[/dim]",
        "verifying_query": "正在理解您的请求...",
        # Files
        "files_title": "📁 结果文件",
        "files_empty": "[yellow]输出目录中没有结果文件。[/yellow]",
        "files_select_prompt": "输入文件编号查看 (或直接回车跳过)",
        # Summary
        "summary_generating": "正在生成摘要...",
        "summary_title": "📋 研究综述",
        "summary_added": "[green]✅ 摘要已添加至: {path}[/green]",
        "summary_no_papers": "[yellow]没有可总结的论文。[/yellow]",
        "auto_summary_toggled": "[green]自动生成摘要: {status}[/green]",
        "arxiv_categories_label": "ArXiv 搜索类别",
        "arxiv_categories_updated": "[green]ArXiv 搜索类别已更新[/green]",
        "categories_instruction": "[bold cyan]↑/↓[/] 移动, [bold cyan]Enter[/] 勾选/取消, [bold cyan]s[/] 保存并退出, [bold cyan]q[/] 取消",
        "select_categories_prompt": "选择类别 (输入数字并用空格/逗号分隔以切换，输入 'all' 全选，'none' 全不选，直接回车完成)",
    },
}

# Special commands for auto-completion
SPECIAL_COMMANDS = [
    "/settings",
    "/quit",
    "/exit",
    "quit",
    "exit",
    "/help",
    "/clear",
    "/reset",
    "/search",
    "/feedback",
    "/memory",
    "/chat",
    "/files",
    "/summary",
    "/categories",
    "?",
]


class PaperResearchCLI:
    """Paper research assistant CLI"""

    def __init__(self):
        self.fetcher = ArxivFetcher()
        self.time_parser = TimeParser()
        self.query_parser = QueryParser()
        self.preference_manager = get_preference_manager()
        self.scorer = InterestScorer(preference_manager=self.preference_manager)
        self.current_papers: list[Paper] = []
        self.query_history: list[str] = []
        # Load saved settings
        self.search_mode = (
            self.preference_manager.get_search_mode() or config.DEFAULT_SEARCH_MODE
        )
        self.lang = self.preference_manager.get_language()
        self.max_workers = (
            self.preference_manager.get_max_workers() or config.MAX_WORKERS
        )

        # Save to local: check saved preference, or use config default
        saved_save_to_local = self.preference_manager.get_save_to_local()
        self.save_to_local = (
            saved_save_to_local
            if saved_save_to_local is not None
            else config.SAVE_TO_LOCAL
        )
        self.first_run = saved_save_to_local is None  # First time user

        # Output directory
        saved_output_dir = self.preference_manager.get_output_dir()
        self.output_dir = (
            Path(saved_output_dir) if saved_output_dir else config.DEFAULT_OUTPUT_DIR
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save results to file
        saved_save_results = self.preference_manager.get_save_results()
        self.save_results = (
            saved_save_results
            if saved_save_results is not None
            else config.SAVE_RESULTS_TO_FILE
        )

        # Maximum display papers
        saved_max_display = self.preference_manager.get_max_display()
        self.max_display = (
            saved_max_display
            if saved_max_display is not None
            else config.MAX_DISPLAY_PAPERS
        )

        # Auto-summary setting
        saved_auto_summary = self.preference_manager.get_auto_summary()
        self.auto_summary = (
            saved_auto_summary
            if saved_auto_summary is not None
            else config.AUTO_SUMMARY
        )

        # Prompt toolkit session for auto-completion and persistent history (max 100)
        history_path = os.path.join(str(config.DATA_DIR), "history.txt")

        # Create key bindings for multi-line input
        kb = KeyBindings()

        @kb.add("escape", "enter")  # Alt/Meta+Enter for newline
        def _(event):
            """Handle Alt+Enter or Escape+Enter - insert newline"""
            event.app.current_buffer.insert_text("\n")

        self.session = PromptSession(
            completer=WordCompleter(
                SPECIAL_COMMANDS,
                ignore_case=True,
                pattern=re.compile(r"[a-zA-Z0-9_/]+"),  # Include / in word pattern
            ),
            history=LimitedFileHistory(history_path),
            complete_while_typing=True,
            multiline=False,  # Disable default multi-line, use Alt+Enter for newlines
            key_bindings=kb,
        )

    def t(self, key: str, **kwargs) -> str:
        """Translate a key based on current language"""
        lang = self.lang or "en"
        return TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key, key).format(**kwargs)

    def _show_menu_selector(
        self, title: str, options: list[tuple[str, str]], current_value: str = None
    ) -> Optional[str]:
        """Generic interactive menu selector with keyboard navigation

        Args:
            title: Menu title
            options: List of (value, label) tuples
            current_value: Currently selected value (optional)

        Returns:
            Selected value or None if cancelled
        """
        from prompt_toolkit.application import Application
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        # State variables
        state = {"cursor_position": 0, "selected_value": None}

        # Find current index
        if current_value:
            for i, (value, _) in enumerate(options):
                if value == current_value:
                    state["cursor_position"] = i
                    break

        def get_formatted_text():
            result = []
            result.append(("class:title", f"╔══ {title} ══╗\n\n"))

            for i, (value, label) in enumerate(options):
                is_current = i == state["cursor_position"]

                if is_current:
                    result.append(("class:current", f" ► {label}\n"))
                else:
                    result.append(("class:option", f"   {label}\n"))

            result.append(("", "\n"))
            if self.lang == "zh":
                result.append(("class:help", "↑↓: 移动 | Enter: 确认 | q/Esc: 取消"))
            else:
                result.append(
                    ("class:help", "↑↓: Move | Enter: Confirm | q/Esc: Cancel")
                )

            return FormattedText(result)

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("c-p")
        def move_up(event):
            state["cursor_position"] = (state["cursor_position"] - 1) % len(options)
            event.app.invalidate()

        @kb.add("down")
        @kb.add("c-n")
        def move_down(event):
            state["cursor_position"] = (state["cursor_position"] + 1) % len(options)
            event.app.invalidate()

        @kb.add("enter")
        def confirm(event):
            state["selected_value"] = options[state["cursor_position"]][0]
            event.app.exit()

        @kb.add("q")
        @kb.add("escape")
        def cancel(event):
            event.app.exit()

        text_control = FormattedTextControl(text=get_formatted_text, focusable=True)
        layout = Layout(HSplit([Window(content=text_control, always_hide_cursor=True)]))

        from prompt_toolkit.styles import Style

        style = Style.from_dict(
            {
                "title": "#00ffff bold",
                "current": "#00ff00 bold bg:#303030",
                "option": "#ffffff",
                "help": "#00ffff",
            }
        )

        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
            style=style,
        )
        app.run()

        return state["selected_value"]

    def select_language(self):
        """Prompt user to select language"""
        options = [
            ("en", "English"),
            ("zh", "中文"),
        ]
        title = "Select Language / 选择语言"

        selected = self._show_menu_selector(title, options, self.lang)

        if selected:
            self.lang = selected
            self.preference_manager.set_language(selected)
            # Re-initialize completer if needed (though commands are same)
            self.session.completer = WordCompleter(
                SPECIAL_COMMANDS,
                ignore_case=True,
                pattern=re.compile(r"[a-zA-Z0-9_/]+"),
            )

            msg = (
                "Language updated to English"
                if selected == "en"
                else "语言已更新为中文"
            )
            console.print(f"[green]✓ {msg}[/green]")

    def select_search_mode(self):
        """Prompt user to select search mode"""
        if self.lang == "zh":
            title = "🔍 搜索模式"
            options = [
                ("keyword", "关键词搜索 - 快速筛选关键词匹配的论文"),
                ("exhaustive", "遍历搜索 - 深度分析所有论文（较慢）"),
            ]
        else:
            title = "🔍 Search Mode"
            options = [
                ("keyword", "Keyword - Quick filtering by keywords"),
                ("exhaustive", "Exhaustive - Deep analysis of all papers (slower)"),
            ]

        selected = self._show_menu_selector(title, options, self.search_mode)

        if selected:
            self.search_mode = selected
            self.preference_manager.set_search_mode(selected)

            new_mode = "Keyword" if selected == "keyword" else "Exhaustive"
            if self.lang == "zh":
                new_mode = "关键词搜索" if selected == "keyword" else "遍历搜索"

            console.print(self.t("search_mode_updated", mode=new_mode))

    def print_welcome(self):
        """Print welcome message in Claude Code style"""
        # Get current search mode for display
        mode_display = "Keyword" if self.search_mode == "keyword" else "Exhaustive"
        if self.lang == "zh":
            mode_display = "关键词" if self.search_mode == "keyword" else "遍历"

        # Create the welcome panel with box drawing characters
        from rich.columns import Columns
        from rich.layout import Layout
        from rich.text import Text

        # Left side - Welcome message
        welcome_text = Text()
        welcome_text.append("Welcome back!\n\n", style="bold white")
        welcome_text.append("  📚  \n", style="bold bright_red")
        welcome_text.append(" 📖📖 \n", style="bold bright_red")
        welcome_text.append("📕📗📘\n\n", style="bold bright_red")
        welcome_text.append(
            f"v1.0.0 · {self.search_mode.capitalize()} Mode\n", style="dim"
        )

        # Display current output directory
        abs_output_dir = os.path.abspath(self.output_dir)
        # Try to make it look nicer if it's in the home directory
        home = os.path.expanduser("~")
        if abs_output_dir.startswith(home):
            display_path = abs_output_dir.replace(home, "~", 1)
        else:
            display_path = abs_output_dir

        # Shorten if too long
        if len(display_path) > 30:
            display_path = "..." + display_path[-27:]

        welcome_text.append(f"{self.t('output_path_label')}: ", style="dim")
        welcome_text.append(f"{display_path}", style="cyan")

        # Right side - Tips and activity
        tips_text = Text()
        tips_text.append(f"{self.t('tips_title')}\n", style="bold bright_yellow")
        tips_text.append(f"{self.t('tips_content')}\n\n", style="white")
        tips_text.append("Recent activity\n", style="bold bright_yellow")

        # Show recent activity if available
        memory = self.preference_manager.get_preference_context()
        if memory and memory.strip():
            memory_preview = memory[:60] + "..." if len(memory) > 60 else memory
            tips_text.append(f"Memory: {memory_preview}", style="dim")
        else:
            tips_text.append("No recent activity", style="dim")

        # Create columns layout
        left_panel = Panel(
            welcome_text,
            border_style="bright_blue",
            padding=(1, 2),
        )
        right_panel = Panel(
            tips_text,
            border_style="bright_blue",
            padding=(1, 2),
        )

        # Print the welcome box
        console.print()
        console.print(
            Panel(
                Columns([left_panel, right_panel], equal=True, expand=True),
                title=f"[bold bright_blue]─── {self.t('welcome_title')} ───[/]",
                border_style="bright_blue",
                padding=(0, 1),
            )
        )
        console.print()

    def print_shortcuts(self):
        """Print available shortcuts"""
        if self.lang == "zh":
            shortcuts = """
[bold]快捷命令[/bold]
  [cyan]/search[/]              切换搜索模式 (关键词/遍历)
  [cyan]/chat[/]                进入对话模式
  [cyan]/chat <内容>[/]         单次对话（不进入持续模式）
  [cyan]/files[/]               查看已保存的结果文件
  [cyan]/summary[/]             生成论文摘要/综述
  [cyan]/feedback[/]            进入反馈模式
  [cyan]/feedback <反馈>[/]     单次反馈（不进入持续模式）
  [cyan]/memory[/]              管理偏好记忆
  [cyan]/categories[/]          管理 arXiv 搜索类别
  [cyan]/settings[/]            调整设置
  [cyan]/help[/]                显示帮助
  [cyan]/clear[/]               清空屏幕
  [cyan]/quit[/]                退出程序

[bold]查询示例[/bold]
  • 找最近一周的大模型论文
  • 过去三天的 RAG 论文
  • multimodal learning papers from last week

[bold]单行命令示例[/bold]
  • /chat 总结最近论文的研究趋势
  • /chat 找出不同主题之间的联系
  • /feedback 我不喜欢 RAG 论文
  • /feedback Paper 1,3 很有趣
"""
        else:
            shortcuts = """
[bold]Shortcuts[/bold]
  [cyan]/search[/]              Toggle search mode (Keyword/Exhaustive)
  [cyan]/chat[/]                Enter chat mode
  [cyan]/chat <query>[/]        One-time chat (no persistent mode)
  [cyan]/files[/]               View saved result files
  [cyan]/summary[/]             Generate paper summary/overview
  [cyan]/feedback[/]            Enter feedback mode
  [cyan]/feedback <text>[/]     One-time feedback (no persistent mode)
  [cyan]/memory[/]              Manage preference memory
  [cyan]/categories[/]          Manage arXiv search categories
  [cyan]/settings[/]            Adjust settings
  [cyan]/help[/]                Show help
  [cyan]/clear[/]               Clear screen
  [cyan]/quit[/]                Exit program

[bold]Query Examples[/bold]
  • Find LLM papers from last week
  • RAG papers from past 3 days
  • 最近一周的大模型论文

[bold]Single-line Command Examples[/bold]
  • /chat Summarize recent research trends
  • /chat Find connections between different topics
  • /feedback I don't like RAG papers
  • /feedback Paper 1,3 are interesting
"""
        console.print(
            Panel(shortcuts, title="[bold]? Shortcuts[/]", border_style="dim")
        )

    def show_category_selector(self):
        """Show interactive category selection with keyboard navigation"""
        from prompt_toolkit.application import Application
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        current_categories = set(
            self.preference_manager.get_arxiv_categories()
            or config.DEFAULT_ARXIV_CATEGORIES
        )

        all_cats_list = []
        for group, cats in config.ALL_ARXIV_CATEGORIES.items():
            for code, desc in cats.items():
                all_cats_list.append((code, desc, group))

        # State dictionary to avoid closure issues
        state = {
            "cursor_position": 0,
            "scroll_offset": 0,
            "saved": False,
            "categories": current_categories,
        }

        def get_formatted_text():
            """Generate the formatted text for display"""
            result = []
            title = (
                self.t("arxiv_categories_label")
                if self.lang == "zh"
                else "ArXiv Search Categories"
            )
            result.append(("class:title", f"╔══ {title} ══╗\n\n"))

            # Visible window
            visible_height = 20
            start_idx = state["scroll_offset"]
            end_idx = min(start_idx + visible_height, len(all_cats_list))

            for i in range(start_idx, end_idx):
                code, desc, group = all_cats_list[i]
                is_selected = code in state["categories"]
                is_current = i == state["cursor_position"]

                # Status icon
                status = "✓" if is_selected else " "

                # Build line
                if is_current:
                    result.append(("class:current-line", f" ► [{status}] "))
                    result.append(("class:current-code", f"{code:<10} "))
                    result.append(("class:current-desc", f"{desc:<35} "))
                    result.append(("class:current-group", f"({group})"))
                    result.append(("", "\n"))
                else:
                    color = "class:selected" if is_selected else "class:unselected"
                    result.append((color, f"   [{status}] "))
                    result.append((color, f"{code:<10} "))
                    result.append(("class:desc", f"{desc:<35} "))
                    result.append(("class:group", f"({group})"))
                    result.append(("", "\n"))

            # Footer
            result.append(("", "\n"))
            result.append(("class:footer", f"Selected: {len(state['categories'])} | "))
            result.append(
                (
                    "class:footer",
                    f"Position: {state['cursor_position'] + 1}/{len(all_cats_list)}\n",
                )
            )

            if self.lang == "zh":
                result.append(
                    (
                        "class:help",
                        "↑↓: 移动 | Space: 切换 | a: 全选 | n: 清空 | Enter: 保存 | q/Esc: 取消",
                    )
                )
            else:
                result.append(
                    (
                        "class:help",
                        "↑↓: Move | Space: Toggle | a: All | n: None | Enter: Save | q/Esc: Cancel",
                    )
                )

            return FormattedText(result)

        # Key bindings
        kb = KeyBindings()

        @kb.add("up")
        def move_up(event):
            if state["cursor_position"] > 0:
                state["cursor_position"] -= 1
                if state["cursor_position"] < state["scroll_offset"]:
                    state["scroll_offset"] = state["cursor_position"]
                event.app.invalidate()

        @kb.add("down")
        def move_down(event):
            if state["cursor_position"] < len(all_cats_list) - 1:
                state["cursor_position"] += 1
                if state["cursor_position"] >= state["scroll_offset"] + 20:
                    state["scroll_offset"] = state["cursor_position"] - 19
                event.app.invalidate()

        @kb.add("c-n")  # Ctrl+N (alternative down)
        def move_down_alt(event):
            move_down(event)

        @kb.add("c-p")  # Ctrl+P (alternative up)
        def move_up_alt(event):
            move_up(event)

        @kb.add(" ")  # Space to toggle
        def toggle_current(event):
            code = all_cats_list[state["cursor_position"]][0]
            if code in state["categories"]:
                state["categories"].remove(code)
            else:
                state["categories"].add(code)
            event.app.invalidate()

        @kb.add("a")  # Select all
        def select_all(event):
            state["categories"].clear()
            state["categories"].update(c[0] for c in all_cats_list)
            event.app.invalidate()

        @kb.add("n")  # Clear all
        def clear_all(event):
            state["categories"].clear()
            event.app.invalidate()

        @kb.add("enter")  # Save and exit
        def save_and_exit(event):
            state["saved"] = True
            event.app.exit()

        @kb.add("q")
        @kb.add("escape")
        def cancel(event):
            event.app.exit()

        # Layout
        text_control = FormattedTextControl(
            text=get_formatted_text,
            focusable=True,
        )

        layout = Layout(
            HSplit(
                [
                    Window(content=text_control, always_hide_cursor=True),
                ]
            )
        )

        # Style
        from prompt_toolkit.styles import Style

        style = Style.from_dict(
            {
                "title": "#00ffff bold",
                "current-line": "bg:#303030",
                "current-code": "#00ff00 bold bg:#303030",
                "current-desc": "#ffffff bg:#303030",
                "current-group": "#808080 bg:#303030",
                "selected": "#00ff00",
                "unselected": "#808080",
                "desc": "#ffffff",
                "group": "#606060",
                "footer": "#ffff00",
                "help": "#00ffff",
            }
        )

        # Application
        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
            style=style,
        )

        # Run the application
        app.run()

        # Save if confirmed
        if state["saved"]:
            self.preference_manager.set_arxiv_categories(list(state["categories"]))
            console.print(self.t("arxiv_categories_updated"))
            console.print(
                f"[bold]Selected: {', '.join(sorted(state['categories']))}[/bold]\n"
            )

    def show_settings_menu(self):
        """Show settings menu with keyboard navigation"""
        from prompt_toolkit.application import Application
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import Layout
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl

        def get_menu_options():
            """Generate menu options dynamically based on current state"""
            save_status = "ON ✓" if self.save_to_local else "OFF ✗"
            save_results_status = "ON ✓" if self.save_results else "OFF ✗"
            auto_summary_status = "ON ✓" if self.auto_summary else "OFF ✗"

            if self.lang == "zh":
                save_status = "开启 ✓" if self.save_to_local else "关闭 ✗"
                save_results_status = "开启 ✓" if self.save_results else "关闭 ✗"
                auto_summary_status = "开启 ✓" if self.auto_summary else "关闭 ✗"

                current_mode = (
                    "关键词搜索" if self.search_mode == "keyword" else "遍历搜索"
                )
                max_display_str = (
                    str(self.max_display) if self.max_display else "不限制"
                )

                categories = (
                    self.preference_manager.get_arxiv_categories()
                    or config.DEFAULT_ARXIV_CATEGORIES
                )

                return [
                    ("language", f"语言 / Language: {self.lang.upper()}"),
                    ("search_mode", f"搜索模式: {current_mode}"),
                    ("max_workers", f"并发数: {self.max_workers}"),
                    ("save_to_local", f"保存用户兴趣和搜索历史: {save_status}"),
                    ("output_dir", f"输出目录: {str(self.output_dir)[-30:]}"),
                    ("save_results", f"保存搜索结果: {save_results_status}"),
                    ("max_display", f"最大显示数: {max_display_str}"),
                    ("auto_summary", f"自动总结: {auto_summary_status}"),
                    ("categories", f"ArXiv 类别: {len(categories)} 个已选"),
                    ("back", "← 返回"),
                ]
            else:
                current_mode = (
                    "Keyword" if self.search_mode == "keyword" else "Exhaustive"
                )
                max_display_str = (
                    str(self.max_display) if self.max_display else "unlimited"
                )

                categories = (
                    self.preference_manager.get_arxiv_categories()
                    or config.DEFAULT_ARXIV_CATEGORIES
                )

                return [
                    ("language", f"Language: {self.lang.upper()}"),
                    ("search_mode", f"Search Mode: {current_mode}"),
                    ("max_workers", f"Max Workers: {self.max_workers}"),
                    ("save_to_local", f"Save Interests & History: {save_status}"),
                    ("output_dir", f"Output Dir: {str(self.output_dir)[-30:]}"),
                    ("save_results", f"Save Results: {save_results_status}"),
                    ("max_display", f"Max Display: {max_display_str}"),
                    ("auto_summary", f"Auto Summary: {auto_summary_status}"),
                    ("categories", f"ArXiv Categories: {len(categories)} selected"),
                    ("back", "← Back"),
                ]

        state = {"cursor_position": 0, "selected_action": None}

        def get_formatted_text():
            options = get_menu_options()
            result = []

            title = "⚙️  Settings" if self.lang != "zh" else "⚙️  设置"
            result.append(("class:title", f"╔══ {title} ══╗\n\n"))

            for i, (action, label) in enumerate(options):
                is_current = i == state["cursor_position"]

                if is_current:
                    result.append(("class:current", f" ► {label}\n"))
                else:
                    result.append(("class:option", f"   {label}\n"))

            result.append(("", "\n"))
            if self.lang == "zh":
                result.append(("class:help", "↑↓: 移动 | Enter: 选择 | q/Esc: 返回"))
            else:
                result.append(("class:help", "↑↓: Move | Enter: Select | q/Esc: Back"))

            return FormattedText(result)

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("c-p")
        def move_up(event):
            options = get_menu_options()
            state["cursor_position"] = (state["cursor_position"] - 1) % len(options)
            event.app.invalidate()

        @kb.add("down")
        @kb.add("c-n")
        def move_down(event):
            options = get_menu_options()
            state["cursor_position"] = (state["cursor_position"] + 1) % len(options)
            event.app.invalidate()

        @kb.add("enter")
        def confirm(event):
            options = get_menu_options()
            state["selected_action"] = options[state["cursor_position"]][0]
            event.app.exit()

        @kb.add("q")
        @kb.add("escape")
        def cancel(event):
            event.app.exit()

        text_control = FormattedTextControl(text=get_formatted_text, focusable=True)
        layout = Layout(HSplit([Window(content=text_control, always_hide_cursor=True)]))

        from prompt_toolkit.styles import Style

        style = Style.from_dict(
            {
                "title": "#00ffff bold",
                "current": "#00ff00 bold bg:#303030",
                "option": "#ffffff",
                "help": "#00ffff",
            }
        )

        app = Application(
            layout=layout,
            key_bindings=kb,
            full_screen=False,
            mouse_support=False,
            style=style,
        )
        app.run()

        # Handle the selected action
        if state["selected_action"] == "language":
            self.select_language()
        elif state["selected_action"] == "search_mode":
            self.select_search_mode()
        elif state["selected_action"] == "max_workers":
            count = Prompt.ask(
                "Max workers" if self.lang != "zh" else "并发数",
                default=str(self.max_workers),
            )
            try:
                self.max_workers = int(count)
                self.preference_manager.set_max_workers(self.max_workers)
                console.print(self.t("workers_updated", count=self.max_workers))
            except ValueError:
                console.print(self.t("invalid_option"))
        elif state["selected_action"] == "save_to_local":
            self.save_to_local = not self.save_to_local
            self.preference_manager.set_save_to_local(self.save_to_local)
            status = "ON" if self.save_to_local else "OFF"
            if self.lang == "zh":
                status = "开启" if self.save_to_local else "关闭"
            console.print(self.t("save_toggled", status=status))
        elif state["selected_action"] == "output_dir":
            path = Prompt.ask(self.t("enter_output_dir"), default=str(self.output_dir))
            self.output_dir = Path(path)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.preference_manager.set_output_dir(str(self.output_dir))
            console.print(self.t("output_dir_updated", path=str(self.output_dir)))
        elif state["selected_action"] == "save_results":
            self.save_results = not self.save_results
            self.preference_manager.set_save_results(self.save_results)
            status = "ON" if self.save_results else "OFF"
            if self.lang == "zh":
                status = "开启" if self.save_results else "关闭"
            console.print(self.t("save_results_toggled", status=status))
        elif state["selected_action"] == "max_display":
            max_display_input = Prompt.ask(
                self.t("enter_max_display"),
                default=(
                    str(self.max_display)
                    if self.max_display
                    else ("unlimited" if self.lang == "en" else "不限制")
                ),
            )
            if max_display_input.lower() in ["unlimited", "不限制", "none"]:
                self.max_display = None
                display_text = "unlimited" if self.lang == "en" else "不限制"
            else:
                try:
                    self.max_display = int(max_display_input)
                    display_text = str(self.max_display)
                except ValueError:
                    console.print(self.t("invalid_option"))
                    return
            self.preference_manager.set_max_display(self.max_display)
            console.print(self.t("max_display_updated", count=display_text))
        elif state["selected_action"] == "auto_summary":
            self.auto_summary = not self.auto_summary
            self.preference_manager.set_auto_summary(self.auto_summary)
            status = "ON" if self.auto_summary else "OFF"
            if self.lang == "zh":
                status = "开启" if self.auto_summary else "关闭"
            console.print(self.t("auto_summary_toggled", status=status))
        elif state["selected_action"] == "categories":
            self.show_category_selector()

    def show_memory_menu(self):
        """Show memory management menu with keyboard navigation"""
        if self.lang == "zh":
            title = "🧠 偏好记忆"
            options = [
                ("view", "查看当前偏好记忆"),
                ("add", "添加新的偏好"),
                ("clear", "清空偏好记忆"),
                ("back", "← 返回"),
            ]
        else:
            title = "🧠 Memory"
            options = [
                ("view", "View Current Memory"),
                ("add", "Add New Preference"),
                ("clear", "Clear Memory"),
                ("back", "← Back"),
            ]

        selected = self._show_menu_selector(title, options)

        if selected == "view":
            # View current memory
            memory = self.preference_manager.get_preference_context()
            if memory and memory.strip():
                console.print(
                    Panel(
                        memory,
                        title=self.t("memory_current_title"),
                        border_style="blue",
                    )
                )
            else:
                console.print(self.t("memory_empty"))
        elif selected == "add":
            # Add to memory
            new_pref = Prompt.ask(self.t("memory_add_prompt"))
            if new_pref.strip():
                self.preference_manager.add_preference_update(
                    f"User preference: {new_pref.strip()}"
                )
                # Trigger memory update
                self.preference_manager.schedule_memory_update(
                    f"User explicitly stated: {new_pref.strip()}",
                    on_complete=self._on_memory_update,
                )
                console.print(self.t("memory_added"))
        elif selected == "clear":
            # Clear memory
            if Confirm.ask(self.t("memory_clear_confirm")):
                self.preference_manager.clear_memory()
                console.print(self.t("memory_cleared"))

    def show_files_list(self):
        """Show list of result files"""
        analyzer = get_outputs_analyzer(self.output_dir)
        file_summaries = analyzer.get_file_summaries()

        if not file_summaries:
            console.print(self.t("files_empty"))
            return

        table = Table(title=self.t("files_title"))
        table.add_column("#", style="cyan", width=4)
        table.add_column("Topic" if self.lang != "zh" else "主题", style="green")
        table.add_column(
            "Papers" if self.lang != "zh" else "论文数", style="yellow", width=8
        )
        table.add_column("Date" if self.lang != "zh" else "日期", style="dim")
        table.add_column("File" if self.lang != "zh" else "文件", style="dim")

        for i, f in enumerate(file_summaries[:20], 1):
            table.add_row(
                str(i),
                f["topic"][:40] + "..." if len(f["topic"]) > 40 else f["topic"],
                str(f["count"]),
                f["date"][:10] if f["date"] else "",
                (
                    f["filename"][:30] + "..."
                    if len(f["filename"]) > 30
                    else f["filename"]
                ),
            )

        console.print(table)
        return file_summaries

    def validate_chat_input(self, query: str) -> tuple[bool, Optional[str]]:
        """Use LLM to validate chat mode input"""
        if query.startswith("/"):
            return True, None

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(self.t("verifying_query"), total=None)

                llm = get_llm_client()
                lang_instruction = (
                    "回复请用中文。" if self.lang == "zh" else "Respond in English."
                )

                system_prompt = f"""You are a helpful assistant for discussing research papers.
Determine if the user's input is a valid question/request about papers, or just a greeting/meaningless input.

If valid (asking about papers, trends, connections, etc.): {{"valid": true, "response": ""}}
If greeting/thanks/meaningless: {{"valid": false, "response": "<brief friendly response and guide them to ask about papers>"}}

{lang_instruction} Keep response under 50 words."""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query.strip()},
                ]

                result = llm.chat_json(messages, temperature=0.3, max_tokens=200)

            is_valid = result.get("valid")
            response = result.get("response", "").strip()

            if is_valid is False and response:
                return False, response

        except Exception:
            pass

        return True, None

    def run_single_chat(self, query: str):
        """Process a single chat query without entering interactive mode"""
        # Validate input first
        should_continue, response_msg = self.validate_chat_input(query)
        if not should_continue:
            if response_msg:
                console.print(response_msg)
            return

        analyzer = get_outputs_analyzer(self.output_dir)
        chat = get_research_chat(self.output_dir)

        # Check if there are any result files
        file_summaries = analyzer.get_file_summaries()
        if not file_summaries:
            console.print(self.t("chat_no_files"))
            return

        try:
            # Process chat query
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(self.t("chat_processing"), total=None)
                response = chat.chat(query, lang=self.lang or "en")
                progress.update(task, completed=True)

            # Display response
            console.print(
                Panel(
                    Markdown(response.content),
                    border_style="bright_cyan",
                )
            )

            # Show search suggestion if needed
            if response.needs_search and response.search_query:
                console.print(
                    self.t("chat_search_suggest", query=response.search_query)
                )

            # Offer to save if appropriate
            if response.should_write:
                if Confirm.ask(self.t("chat_write_confirm"), default=False):
                    filepath = chat.write_to_file(
                        response.content,
                        target_file=response.target_file,
                        new_file_name=response.new_file_name,
                        section_title=query[:50],
                    )
                    console.print(self.t("chat_saved", path=str(filepath)))

        except Exception as e:
            console.print(self.t("error_msg", error=str(e)))

    def run_chat_mode(self):
        """Run interactive chat mode for discussing papers"""
        analyzer = get_outputs_analyzer(self.output_dir)
        chat = get_research_chat(self.output_dir)

        # Check if there are any result files
        file_summaries = analyzer.get_file_summaries()
        if not file_summaries:
            console.print(self.t("chat_no_files"))
            return

        # Show available files
        console.print(
            Panel(
                f"{self.t('chat_mode_desc')}\n\n"
                f"[dim]Available files: {len(file_summaries)}[/dim]",
                title=self.t("chat_mode_title"),
                border_style="bright_cyan",
            )
        )

        # Clear chat history for new session
        chat.clear_history()

        while True:
            try:
                query = self.session.prompt(self.t("chat_prompt")).strip()

                if not query:
                    continue

                if query.lower() in ["/exit", "/quit", "exit", "quit", "/退出", "退出"]:
                    console.print(self.t("chat_exit"))
                    break

                if query.lower() == "/files":
                    self.show_files_list()
                    continue

                if query.lower() == "/clear":
                    chat.clear_history()
                    console.print(self.t("reset_msg"))
                    continue

                # Validate chat input
                should_continue, response_msg = self.validate_chat_input(query)
                if not should_continue:
                    if response_msg:
                        console.print(response_msg)
                    continue

                # Process chat query
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    task = progress.add_task(self.t("chat_processing"), total=None)
                    response = chat.chat(query, lang=self.lang or "en")
                    progress.update(task, completed=True)

                # Display response
                console.print(
                    Panel(
                        Markdown(response.content),
                        border_style="bright_cyan",
                    )
                )

                # Show search suggestion if needed
                if response.needs_search and response.search_query:
                    console.print(
                        self.t("chat_search_suggest", query=response.search_query)
                    )

                # Offer to save if appropriate
                if response.should_write:
                    if Confirm.ask(self.t("chat_write_confirm"), default=False):
                        filepath = chat.write_to_file(
                            response.content,
                            target_file=response.target_file,
                            new_file_name=response.new_file_name,
                            section_title=query[:50],
                        )
                        console.print(self.t("chat_saved", path=str(filepath)))

            except EOFError:
                break
            except KeyboardInterrupt:
                console.print(self.t("chat_exit"))
                break
            except Exception as e:
                console.print(self.t("error_msg", error=str(e)))
                continue

    def generate_and_show_summary(
        self, papers: list[Paper], topic: str
    ) -> Optional[str]:
        """Generate and display a summary for the papers"""
        if not papers:
            console.print(self.t("summary_no_papers"))
            return None

        # Show which topic is being summarized
        topic_display = f"[bold cyan]{topic}[/bold cyan]"
        if self.lang == "zh":
            console.print(
                f"\n[dim]正在生成关于主题：{topic_display} 的研究综述...[/dim]"
            )
        else:
            console.print(
                f"\n[dim]Generating research summary for topic: {topic_display}...[/dim]"
            )

        chat = get_research_chat(self.output_dir)

        # Convert Paper objects to ParsedPaper-like format for the summary generator
        from src.outputs_analyzer import ParsedPaper as PP

        parsed_papers = []
        for p in papers:
            parsed_papers.append(
                PP(
                    title=p.title,
                    score=p.interest_score,
                    arxiv_id=p.arxiv_id,
                    published=p.published.strftime("%Y-%m-%d") if p.published else "",
                    authors=p.authors,
                    categories=p.categories,
                    link=p.arxiv_url,
                    score_reason=p.interest_reason or "",
                    abstract=p.abstract,
                    source_file="current_search",
                    topic=topic or "General",
                )
            )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(self.t("summary_generating"), total=None)
            summary = chat.generate_summary(
                parsed_papers,
                topic=topic or "General",
                lang=self.lang or "en",
                max_papers=config.SUMMARY_TOP_PAPERS,
            )
            progress.update(task, completed=True)

        # Display summary
        console.print(
            Panel(
                Markdown(summary),
                title=self.t("summary_title"),
                border_style="bright_green",
            )
        )

        return summary

    def generate_summary_for_files(self, files: Optional[List[str]] = None):
        """Generate summary for existing result files"""
        analyzer = get_outputs_analyzer(self.output_dir)
        chat = get_research_chat(self.output_dir)

        if files:
            # Load specified files
            all_papers = []
            topics = []
            for filepath in analyzer.list_result_files():
                if filepath.name in files:
                    result = analyzer.parse_result_file(filepath)
                    all_papers.extend(result.papers)
                    if result.topic not in topics:
                        topics.append(result.topic)
            topic = ", ".join(topics) if topics else "Multiple topics"
        else:
            # Use most recent file
            file_list = analyzer.list_result_files()
            if not file_list:
                console.print(self.t("files_empty"))
                return
            result = analyzer.parse_result_file(file_list[0])
            all_papers = result.papers
            topic = result.topic

        if not all_papers:
            console.print(self.t("summary_no_papers"))
            return

        # Show which topic is being summarized
        topic_display = f"[bold cyan]{topic}[/bold cyan]"
        if self.lang == "zh":
            console.print(
                f"\n[dim]正在生成关于主题：{topic_display} 的研究综述...[/dim]"
            )
        else:
            console.print(
                f"\n[dim]Generating research summary for topic: {topic_display}...[/dim]"
            )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(self.t("summary_generating"), total=None)
            summary = chat.generate_summary(
                all_papers,
                topic=topic,
                lang=self.lang or "en",
                max_papers=config.SUMMARY_TOP_PAPERS,
            )
            progress.update(task, completed=True)

        console.print(
            Panel(
                Markdown(summary),
                title=self.t("summary_title"),
                border_style="bright_green",
            )
        )

    def validate_and_handle_query(self, query: str) -> tuple[bool, Optional[str]]:
        """
        Use LLM to validate user query and provide intelligent responses

        Returns:
            (should_continue, response_message)
            - should_continue: True if query should be processed normally
            - response_message: Message to show user (if any)
        """
        # Skip validation for commands
        if query.startswith("/"):
            return True, None

        query_stripped = query.strip()

        # Use LLM to intelligently handle the query
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,  # Remove when finished
            ) as progress:
                progress.add_task(self.t("verifying_query"), total=None)

                llm = get_llm_client()

                lang_instruction = (
                    "MUST respond in Chinese (简体中文)."
                    if self.lang == "zh"
                    else "MUST respond in English."
                )

                system_prompt = f"""You are a helpful assistant for a paper search tool.

Analyze the user's input and classify it:

1. **Greeting/Social** ("hello", "hi", "thanks", "你好", "谢谢", etc.)
   → valid=false, brief friendly response

2. **Meaningless** (random text, "test", "aaa", "???", etc.)
   → valid=false, ask them to describe what papers they want

3. **Incomplete query** (too vague, missing key info)
   → valid=false, ask ONE short clarifying question

4. **Valid search query** (has clear topic/keyword OR time range)
   → valid=true, response=""

{lang_instruction}

Return JSON:
{{
    "valid": <true or false>,
    "response": "<brief message if invalid, empty if valid>"
}}"""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query_stripped},
                ]

                result = llm.chat_json(messages, temperature=0.2, max_tokens=300)

            is_valid = result.get("valid")
            response = result.get("response", "").strip()

            # If validation returned false, show the response
            if is_valid is False:
                if response:
                    return False, response
                else:
                    # Fallback if LLM didn't provide a response
                    if self.lang == "zh":
                        return False, "请描述您想搜索的论文主题。"
                    else:
                        return (
                            False,
                            "Please describe the paper topics you want to search.",
                        )

            # If valid is explicitly True, continue with search
            if is_valid is True:
                return True, None

        except Exception as e:
            # If LLM fails, continue with normal processing
            pass

        return True, None

    def parse_user_query(self, query: str) -> ParsedQuery:
        """Parse user's natural language query"""
        if not query.strip():
            return ParsedQuery(original_query=query)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(self.t("parsing_query"), total=None)
            parsed = self.query_parser.parse(query, history=self.query_history)
            progress.update(task, completed=True)

        return parsed

    def fetch_papers(
        self, start_date: datetime, end_date: datetime, topic: Optional[str] = None
    ) -> tuple[list[Paper], Optional[str]]:
        """Fetch papers, returns (papers, cleaned_topic)"""
        # Expand topic into keywords if provided
        keywords = None
        cleaned_topic = topic

        # Only use keywords in "keyword" search mode
        if self.search_mode == "keyword" and topic and topic.strip():
            try:
                topic_expander = get_topic_expander()
                cleaned_topic, keywords = topic_expander.expand_with_fallback(
                    topic, self.lang or "en"
                )
                if keywords:
                    kw_display = ", ".join(keywords[:3])
                    if len(keywords) > 3:
                        kw_display += "..."
                    console.print(
                        f"[dim]🔍 {self.t('search_keywords')}: {kw_display}[/dim]"
                    )
                # Show cleaned topic if it's different from original
                if cleaned_topic != topic:
                    console.print(
                        f"[dim]✨ {self.t('cleaned_topic')}: {cleaned_topic}[/dim]"
                    )
            except Exception as e:
                # If expansion fails, continue without keywords
                console.print(
                    f"[dim yellow]⚠️  Keyword expansion failed, searching all papers[/dim yellow]"
                )
        elif self.search_mode == "exhaustive":
            console.print(
                f"[dim]📚 {self.t('search_mode')}: Exhaustive (downloading all papers in range)[/dim]"
                if self.lang == "en"
                else f"[dim]📚 搜索模式: 遍历（下载时间范围内所有论文）[/dim]"
            )

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(self.t("fetching_papers"), total=None)

            def update_fetch_progress(count):
                if self.lang == "zh":
                    progress.update(
                        task,
                        description=f"{self.t('fetching_papers')} (已获取 {count} 篇)",
                    )
                else:
                    progress.update(
                        task,
                        description=f"{self.t('fetching_papers')} ({count} fetched)",
                    )

            diag = None
            if self.search_mode == "exhaustive":
                papers, diag = self.fetcher.fetch_all_papers(
                    start_date,
                    end_date,
                    include_all=True,
                    on_progress=update_fetch_progress,
                )
            else:
                papers = self.fetcher.fetch_papers(
                    start_date,
                    end_date,
                    max_results=config.MAX_RESULTS,
                    keywords=keywords,
                    include_all=False,
                    on_progress=update_fetch_progress,
                )
            progress.update(task, completed=True)

        if self.search_mode == "exhaustive":
            # Show total papers in date range (before topic filtering)
            console.print(self.t("exhaustive_total_count", count=len(papers)))

            # Show diagnostic info if no papers found
            if len(papers) == 0 and diag:
                console.print(
                    self.t(
                        "exhaustive_diag",
                        raw=diag["raw_count"],
                        too_old=diag["too_old_count"],
                        too_new=diag["too_new_count"],
                        first_date=(
                            diag["first_paper_date"].strftime("%Y-%m-%d")
                            if diag["first_paper_date"]
                            else "N/A"
                        ),
                        last_date=(
                            diag["last_paper_date"].strftime("%Y-%m-%d")
                            if diag["last_paper_date"]
                            else "N/A"
                        ),
                    )
                )
        else:
            console.print(self.t("fetched_papers_count", count=len(papers)))

        return papers, cleaned_topic

    def score_papers(
        self,
        papers: list[Paper],
        topic: Optional[str] = None,
    ) -> list[Paper]:
        """Score papers"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=console,
        ) as progress:
            task = progress.add_task(self.t("evaluating_papers"), total=len(papers))

            def update_progress(current, total):
                progress.update(task, completed=current)

            scored_papers = self.scorer.score_papers(
                papers,
                topic=topic,
                use_preferences=True,
                max_workers=self.max_workers,
                progress_callback=update_progress,
                lang=self.lang or "en",
            )

        return scored_papers

    def display_results(
        self,
        papers: list[Paper],
        show_all: bool = False,
        threshold: float = config.INTEREST_THRESHOLD,
    ):
        """Display results"""
        sorted_papers = sort_papers_by_interest(papers)

        if not show_all:
            displayed_papers = filter_papers_by_threshold(sorted_papers, threshold)
        else:
            displayed_papers = sorted_papers

        if not displayed_papers:
            console.print(self.t("no_matching_papers"))
            return

        # Apply max display limit
        total_count = len(displayed_papers)
        if self.max_display and len(displayed_papers) > self.max_display:
            displayed_papers = displayed_papers[: self.max_display]
            if self.lang == "zh":
                console.print(
                    f"\n📊 显示前 [bold]{len(displayed_papers)}[/bold] 篇最相关的论文（共 {total_count} 篇，阈值: {threshold}分）\n"
                )
            else:
                console.print(
                    f"\n📊 Showing top [bold]{len(displayed_papers)}[/bold] most relevant papers (Total: {total_count}, Threshold: {threshold})\n"
                )
        else:
            console.print(
                self.t(
                    "showing_papers_count",
                    count=len(displayed_papers),
                    threshold=threshold,
                )
            )

        for i, paper in enumerate(displayed_papers, 1):
            if paper.interest_score >= 8:
                score_color = "green"
                emoji = "🔥"
            elif paper.interest_score >= 6:
                score_color = "yellow"
                emoji = "⭐"
            else:
                score_color = "dim"
                emoji = "📄"

            content = f"""[bold]{paper.title}[/bold]

[dim]{self.t('authors_label')}:[/dim] {', '.join(paper.authors[:3])}{'...' if len(paper.authors) > 3 else ''}
[dim]{self.t('categories_label')}:[/dim] {', '.join(paper.categories)}
[dim]{self.t('published_label')}:[/dim] {paper.published.strftime('%Y-%m-%d')}

[dim]{self.t('abstract_label')}:[/dim]
{paper.abstract[:400]}{'...' if len(paper.abstract) > 400 else ''}

[{score_color}]{self.t('score_reason_label')}: {paper.interest_reason}[/{score_color}]

[dim]{self.t('link_label')}:[/dim] {paper.arxiv_url}
"""

            panel = Panel(
                content,
                title=f"{emoji} #{i} | Score: [{score_color}]{paper.interest_score:.1f}[/{score_color}] | {paper.arxiv_id}",
                border_style=score_color,
            )
            console.print(panel)

        self.current_papers = displayed_papers

    def export_results(
        self,
        papers: list[Paper],
        topic: Optional[str] = None,
        summary: Optional[str] = None,
    ):
        """Export results to a Markdown file"""
        if not papers or not self.save_results:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = "".join([c if c.isalnum() else "_" for c in (topic or "general")])
        filename = f"results_{safe_topic}_{timestamp}.md"
        filepath = Path(os.path.join(str(self.output_dir), filename))

        # Ensure directory exists before writing
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {self.t('export_title')}\n\n")
            f.write(
                f"- **{self.t('export_date')}**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )
            f.write(f"- **{self.t('export_topic')}**: {topic or 'General'}\n")
            f.write(f"- **{self.t('export_count')}**: {len(papers)}\n\n")

            # Add summary if provided
            if summary:
                f.write(f"---\n\n")
                f.write(f"## {self.t('summary_title')}\n\n")
                f.write(f"{summary}\n\n")

            f.write(f"---\n\n")

            for i, paper in enumerate(papers, 1):
                f.write(f"## {i}. {paper.title}\n\n")
                f.write(f"- **{self.t('export_score')}**: {paper.interest_score:.1f}\n")
                f.write(f"- **{self.t('export_arxiv_id')}**: {paper.arxiv_id}\n")
                f.write(
                    f"- **{self.t('published_label')}**: {paper.published.strftime('%Y-%m-%d')}\n"
                )
                f.write(
                    f"- **{self.t('authors_label')}**: {', '.join(paper.authors)}\n"
                )
                f.write(
                    f"- **{self.t('categories_label')}**: {', '.join(paper.categories)}\n"
                )
                f.write(f"- **{self.t('link_label')}**: {paper.arxiv_url}\n\n")
                f.write(
                    f"### {self.t('score_reason_label')}\n{paper.interest_reason}\n\n"
                )
                f.write(f"### {self.t('abstract_label')}\n{paper.abstract}\n\n")
                f.write(f"---\n\n")

        console.print(self.t("results_saved", path=filepath))
        return filepath

    def _on_memory_update(self, notification: str):
        """Callback for memory update notifications"""
        if notification:
            console.print(f"\n[dim]{notification}[/dim]")

    def validate_feedback_input(self, feedback: str) -> tuple[bool, Optional[str]]:
        """Use LLM to validate feedback input"""
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                progress.add_task(self.t("verifying_query"), total=None)

                llm = get_llm_client()
                lang_instruction = (
                    "回复请用中文。" if self.lang == "zh" else "Respond in English."
                )

                system_prompt = f"""You are a helpful assistant collecting feedback about research papers.
Determine if the user's input is valid feedback (expressing interest/disinterest in papers or topics), or just a greeting/meaningless input.

If valid feedback: {{"valid": true, "response": ""}}
If greeting/thanks/meaningless: {{"valid": false, "response": "<brief friendly response and guide them to provide paper feedback>"}}

{lang_instruction} Keep response under 50 words."""

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": feedback.strip()},
                ]

                result = llm.chat_json(messages, temperature=0.3, max_tokens=200)

            is_valid = result.get("valid")
            response = result.get("response", "").strip()

            if is_valid is False and response:
                return False, response

        except Exception:
            pass

        return True, None

    def handle_feedback(self, feedback: Optional[str] = None):
        """Handle user feedback"""
        if feedback is None:
            console.print(f"\n{self.t('feedback_mode_entered')}")
            console.print(self.t("feedback_instruction"))
            feedback = Prompt.ask("> ").strip()

        if not feedback:
            return

        # Validate feedback input
        should_continue, response_msg = self.validate_feedback_input(feedback)
        if not should_continue:
            if response_msg:
                console.print(response_msg)
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(self.t("parsing_feedback"), total=None)
            parsed = self.scorer.parse_feedback(feedback, self.current_papers)
            progress.update(task, completed=True)

        feedbacks = parsed.get("feedbacks", [])
        keywords = parsed.get("extracted_keywords", {})

        if feedbacks and self.save_to_local:
            console.print(self.t("parsed_feedback_count", count=len(feedbacks)))
            for fb in feedbacks:
                idx = fb.get("paper_index", 0) - 1
                if 0 <= idx < len(self.current_papers):
                    paper = self.current_papers[idx]
                    fb_type = fb.get("feedback_type", "neutral")
                    reason = fb.get("reason", "")

                    self.preference_manager.add_feedback(
                        paper_id=paper.arxiv_id,
                        paper_title=paper.title,
                        feedback_type=fb_type,
                        feedback_reason=reason,
                    )

        # Build memory update from feedback
        memory_updates = []
        if feedbacks:
            for fb in feedbacks:
                fb_type = fb.get("feedback_type", "")
                reason = fb.get("reason", "")
                if fb_type == "interested" and reason:
                    memory_updates.append(
                        f"User is interested in papers about: {reason}"
                    )
                elif fb_type == "not_interested" and reason:
                    memory_updates.append(f"User is NOT interested in: {reason}")

        for kw in keywords.get("interested", []):
            memory_updates.append(f"User is interested in: {kw}")
        for kw in keywords.get("not_interested", []):
            memory_updates.append(f"User is NOT interested in: {kw}")

        # Also add raw feedback as context
        if (
            feedback
            and not feedbacks
            and not keywords.get("interested")
            and not keywords.get("not_interested")
        ):
            memory_updates.append(f"User feedback: {feedback}")

        if memory_updates and self.save_to_local:
            console.print(self.t("feedback_saved"))
            # Schedule memory update in background with notification
            self.preference_manager.schedule_memory_update(
                "\n".join(memory_updates), on_complete=self._on_memory_update
            )

    def run_interactive(self):
        """Run interactive session"""
        # First time setup
        if not self.lang:
            self.select_language()

        if self.first_run:
            self.save_to_local = Confirm.ask(
                self.t("first_time_save_prompt"), default=True
            )
            self.preference_manager.set_save_to_local(self.save_to_local)
            self.first_run = False

        self.print_welcome()

        is_first_search = True

        while True:
            try:
                # Show shortcuts hint on first search
                if is_first_search:
                    console.print(f"\n[dim]{self.t('shortcuts_hint')}[/dim]")
                else:
                    console.print()  # Just a blank line

                # Get user query using prompt_toolkit for auto-completion
                prompt_text = self.t("main_prompt")

                # Using rich to print the prompt style because prompt_toolkit's prompt is plain text usually
                # We can use formatted text in prompt_toolkit but let's keep it simple
                query = self.session.prompt(prompt_text).strip()

                # Ignore empty input
                if not query:
                    continue

                # Handle special commands
                if query.lower() in [
                    "/quit",
                    "/exit",
                    "quit",
                    "exit",
                    "/q",
                    "/退出",
                    "q",
                    "退出",
                ]:
                    break

                if query.lower() in ["/help", "?", "？"]:
                    self.print_shortcuts()
                    continue

                if query.lower() == "/clear":
                    console.clear()
                    continue

                if query.lower() == "/reset":
                    self.query_history = []
                    console.print(self.t("reset_msg"))
                    continue

                if query.lower() == "/search":
                    self.select_search_mode()
                    continue

                if query.lower() == "/settings":
                    self.show_settings_menu()
                    continue

                if query.lower() == "/memory":
                    self.show_memory_menu()
                    continue

                if query.lower() == "/chat" or query.lower().startswith("/chat "):
                    chat_content = (
                        query[5:].strip() if query.lower().startswith("/chat ") else ""
                    )
                    if not chat_content:
                        # Enter interactive chat mode
                        self.run_chat_mode()
                    else:
                        # Single-line chat mode
                        self.run_single_chat(chat_content)
                    continue

                if query.lower() == "/files":
                    self.show_files_list()
                    continue

                if query.lower() == "/summary" or query.lower().startswith("/summary "):
                    # Parse optional file arguments
                    args = (
                        query[8:].strip()
                        if query.lower().startswith("/summary ")
                        else ""
                    )
                    files = [f.strip() for f in args.split(",")] if args else None
                    self.generate_summary_for_files(
                        files if files and files[0] else None
                    )
                    continue

                if query.lower() == "/categories":
                    self.show_category_selector()
                    continue

                if query.lower() == "/feedback" or query.lower().startswith(
                    "/feedback "
                ):
                    feedback_content = (
                        query[10:].strip()
                        if query.lower().startswith("/feedback ")
                        else ""
                    )
                    if not feedback_content:
                        # Enter interactive feedback mode
                        self.handle_feedback()
                    else:
                        # Single-line feedback mode
                        self.handle_feedback(feedback=feedback_content)
                    continue

                # Validate and handle simple queries (before parsing)
                should_continue, response_msg = self.validate_and_handle_query(query)
                if not should_continue:
                    if response_msg:
                        console.print(response_msg)
                    continue  # Skip to next iteration, don't parse or search

                # Parse the query
                parsed = self.parse_user_query(query)

                # Update history with meaningful queries
                if query.strip() and not query.startswith("/"):
                    self.query_history.append(query)
                    if len(self.query_history) > 10:  # Keep only last 10
                        self.query_history.pop(0)

                # Debug: show parsed result (always show to verify LLM parsing)
                console.print(
                    f"[dim]🔍 LLM Parsed - Time: '{parsed.time_range}' | Topic: '{parsed.topic}'[/dim]"
                )

                # Determine time range
                start_date, end_date = None, None
                if parsed.start_date and parsed.end_date:
                    start_date = self.time_parser.parse_date(parsed.start_date)
                    end_date = self.time_parser.parse_date(parsed.end_date)

                if not start_date or not end_date:
                    if parsed.has_time and parsed.time_range:
                        time_str = parsed.time_range
                    else:
                        # Need to ask for time range
                        time_str = Prompt.ask(self.t("ask_time_range"), default="today")
                    start_date, end_date = self.time_parser.parse(time_str)

                console.print(
                    self.t(
                        "time_range_display",
                        start=start_date.strftime("%Y-%m-%d"),
                        end=end_date.strftime("%Y-%m-%d"),
                    )
                )

                # Determine topic
                if parsed.has_topic and parsed.topic:
                    topic = parsed.topic
                    console.print(self.t("topic_display", topic=topic))
                elif not parsed.has_topic and query.strip():
                    # Query exists but no topic detected - might be just time, ask for topic
                    topic = Prompt.ask(self.t("ask_topic"), default="")
                    topic = topic if topic.strip() else None
                else:
                    # Empty query or using defaults
                    topic = None
                    pref_summary = self.preference_manager.get_preference_summary()
                    if pref_summary not in [
                        "No preference records found",
                        "暂无偏好记录",
                    ]:
                        console.print(self.t("using_saved_prefs"))

                # Fetch papers
                papers, cleaned_topic = self.fetch_papers(start_date, end_date, topic)

                if not papers:
                    console.print(self.t("no_papers_found"))
                    is_first_search = False
                    continue

                # Coarse title filter in exhaustive mode
                if self.search_mode == "exhaustive" and (cleaned_topic or topic):
                    with Progress(
                        SpinnerColumn(),
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        console=console,
                    ) as progress:
                        task = progress.add_task(
                            self.t("title_filtering"), total=len(papers)
                        )

                        def update_filter_progress(current, total):
                            progress.update(task, completed=current)

                        papers = self.scorer.filter_papers_by_title(
                            papers,
                            topic=cleaned_topic or topic,
                            batch_size=20,
                            progress_callback=update_filter_progress,
                            max_workers=self.max_workers,
                        )
                    console.print(self.t("title_filtered_count", count=len(papers)))

                # Score papers using cleaned topic
                scored_papers = self.score_papers(papers, cleaned_topic or topic)

                # Record query
                if self.save_to_local:
                    self.preference_manager.add_query_record(
                        topic=topic or ("Default" if self.lang == "en" else "默认"),
                        time_range=f"{start_date.date()} - {end_date.date()}",
                        results_count=len(scored_papers),
                    )

                # Display results
                self.display_results(scored_papers)

                # Generate summary if auto_summary is enabled
                summary = None
                if self.auto_summary and self.current_papers:
                    summary = self.generate_and_show_summary(
                        self.current_papers, cleaned_topic or topic
                    )

                # Export to file
                self.export_results(
                    self.current_papers, cleaned_topic or topic, summary=summary
                )

                is_first_search = False

            except EOFError:
                break
            except KeyboardInterrupt:
                console.print(self.t("interrupt_msg"))
                break
            except ConnectionError as e:
                error_text = str(e)
                console.print(f"\n[bold red]🌐 {self.t('network_error')}[/bold red]\n")
                console.print(f"[red]{error_text}[/red]\n")
                is_first_search = False
                continue
            except PermissionError as e:
                error_text = str(e)
                console.print(
                    f"\n[bold red]🔑 {self.t('permission_error')}[/bold red]\n"
                )
                console.print(f"[red]{error_text}[/red]\n")
                is_first_search = False
                continue
            except Exception as e:
                console.print(self.t("error_msg", error=str(e)))
                is_first_search = False
                continue

        console.print(self.t("exit_msg"))

    def run_once(
        self,
        time_range: str,
        topic: Optional[str] = None,
        show_all: bool = False,
        threshold: float = config.INTEREST_THRESHOLD,
        save: bool = True,
        max_workers: Optional[int] = None,
    ):
        """Run once (CLI mode)"""
        self.save_to_local = save
        if max_workers:
            self.max_workers = max_workers
        if not self.lang:
            self.lang = "en"

        try:
            start_date, end_date = self.time_parser.parse(time_range)
            console.print(
                self.t(
                    "time_range_display",
                    start=start_date.strftime("%Y-%m-%d"),
                    end=end_date.strftime("%Y-%m-%d"),
                )
            )

            papers, cleaned_topic = self.fetch_papers(start_date, end_date, topic)

            if not papers:
                console.print(self.t("no_papers_found"))
                return

            if self.search_mode == "exhaustive" and (cleaned_topic or topic):
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        self.t("title_filtering"), total=len(papers)
                    )

                    def update_filter_progress(current, total):
                        progress.update(task, completed=current)

                    papers = self.scorer.filter_papers_by_title(
                        papers,
                        topic=cleaned_topic or topic,
                        batch_size=20,
                        progress_callback=update_filter_progress,
                        max_workers=self.max_workers,
                    )
                console.print(self.t("title_filtered_count", count=len(papers)))

            scored_papers = self.score_papers(papers, cleaned_topic or topic)

            if self.save_to_local:
                self.preference_manager.add_query_record(
                    topic=topic or "Default",
                    time_range=f"{start_date.date()} - {end_date.date()}",
                    results_count=len(scored_papers),
                )

            self.display_results(scored_papers, show_all=show_all, threshold=threshold)

            # Generate summary if auto_summary is enabled
            summary = None
            if self.auto_summary and self.current_papers:
                summary = self.generate_and_show_summary(
                    self.current_papers, cleaned_topic or topic
                )

            # Export to file
            self.export_results(self.current_papers, topic, summary=summary)
        except ConnectionError as e:
            error_text = str(e)
            console.print(f"\n[bold red]❌ {self.t('network_error')}[/bold red]\n")
            console.print(f"[red]{error_text}[/red]\n")
            sys.exit(1)
        except PermissionError as e:
            error_text = str(e)
            console.print(f"\n[bold red]❌ {self.t('permission_error')}[/bold red]\n")
            console.print(f"[red]{error_text}[/red]\n")
            sys.exit(1)
        except Exception as e:
            error_text = str(e)
            console.print(f"\n[bold red]❌ {self.t('general_error')}[/bold red]\n")
            console.print(f"[red]{error_text}[/red]\n")
            sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="PaperPal - Discover interesting AI papers from arXiv"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # search command
    search_parser = subparsers.add_parser("search", help="Search for papers")
    search_parser.add_argument(
        "-t",
        "--time",
        default="today",
        help="Time range, e.g., today, week, month, 'last 3 days'",
    )
    search_parser.add_argument(
        "-T", "--topic", default=None, help="Description of interest topics"
    )
    search_parser.add_argument(
        "-a", "--all", action="store_true", help="Show all results"
    )
    search_parser.add_argument(
        "--threshold",
        type=float,
        default=config.INTEREST_THRESHOLD,
        help=f"Score threshold (default: {config.INTEREST_THRESHOLD})",
    )
    search_parser.add_argument(
        "--mode",
        choices=["keyword", "exhaustive"],
        default=None,
        help="Search mode: keyword (fast) or exhaustive (thorough) (default: last used)",
    )
    search_parser.add_argument(
        "-w",
        "--max-workers",
        type=int,
        default=config.MAX_WORKERS,
        help=f"Max workers (default: {config.MAX_WORKERS})",
    )
    search_parser.add_argument(
        "--no-save", action="store_true", help="Don't save this query"
    )

    # interactive command
    subparsers.add_parser("interactive", help="Start interactive session")

    # chat command
    chat_parser = subparsers.add_parser(
        "chat", help="Start chat mode to discuss papers"
    )
    chat_parser.add_argument(
        "--files",
        nargs="*",
        help="Specific result files to include in context",
    )

    # summary command
    summary_parser = subparsers.add_parser(
        "summary", help="Generate summary for papers"
    )
    summary_parser.add_argument(
        "--files",
        nargs="*",
        help="Specific result files to summarize (default: most recent)",
    )

    # preferences command
    pref_parser = subparsers.add_parser("preferences", help="Manage preferences")
    pref_parser.add_argument("--show", action="store_true", help="Show preferences")
    pref_parser.add_argument(
        "--clear-history", action="store_true", help="Clear history"
    )
    pref_parser.add_argument("--clear-all", action="store_true", help="Clear all")
    pref_parser.add_argument("--add-topic", help="Add interested topic")
    pref_parser.add_argument("--add-not-topic", help="Add not interested topic")
    pref_parser.add_argument("--set-custom", help="Set custom preferences")
    pref_parser.add_argument("--set-lang", choices=["en", "zh"], help="Set language")
    pref_parser.add_argument(
        "--set-mode", choices=["keyword", "exhaustive"], help="Set default search mode"
    )
    pref_parser.add_argument("--set-workers", type=int, help="Set max workers")
    pref_parser.add_argument(
        "--set-save", choices=["on", "off"], help="Set save to local"
    )
    pref_parser.add_argument("--set-output-dir", help="Set output directory")
    pref_parser.add_argument(
        "--set-save-results",
        choices=["on", "off"],
        help="Set whether to save results to file",
    )
    pref_parser.add_argument(
        "--set-max-display",
        help="Set max display papers (number or 'unlimited')",
    )
    pref_parser.add_argument(
        "--set-auto-summary",
        choices=["on", "off"],
        help="Set whether to auto-generate summary for search results",
    )

    # Memory management options
    pref_parser.add_argument(
        "--show-memory", action="store_true", help="Show preference memory"
    )
    pref_parser.add_argument(
        "--clear-memory", action="store_true", help="Clear preference memory"
    )
    pref_parser.add_argument("--add-memory", help="Add to preference memory")

    return parser


def check_and_setup_env():
    """Check if API key is set, if not prompt user and save to .env"""
    env_path = Path(os.path.join(str(config.PROJECT_ROOT), ".env"))

    # Reload config to get latest env vars
    from dotenv import load_dotenv, set_key

    # Try to load existing .env if it exists but wasn't loaded
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("OPENAI_API_KEY") or config.OPENAI_API_KEY

    if not api_key:
        console.print(
            Panel(
                "[bold yellow]Welcome to PaperPal! / 欢迎使用 PaperPal！[/bold yellow]\n\n"
                "It looks like your API key is not configured yet.\n"
                "您的 API 密钥尚未配置。\n\n"
                "You can use any OpenAI-compatible API (e.g. OpenAI, DeepSeek, local LLMs).\n"
                "您可以使用任何兼容 OpenAI 接口的服务（如 OpenAI, DeepSeek, 本地大模型等）。",
                title="First-time Setup / 首次设置",
                border_style="bright_blue",
            )
        )

        api_key = Prompt.ask(
            "[bold cyan]Enter your API Key / 输入 API 密钥[/bold cyan]"
        ).strip()
        while not api_key:
            api_key = Prompt.ask(
                "[red]API Key cannot be empty. / 密钥不能为空。[/red]"
            ).strip()

        base_url = Prompt.ask(
            "[bold cyan]Enter API Base URL / 输入 API 基础 URL[/bold cyan]",
            default="https://api.openai.com/v1",
        ).strip()

        model = Prompt.ask(
            "[bold cyan]Enter Model Name / 输入模型名称[/bold cyan]",
            default="gpt-4o-mini",
        ).strip()

        # Save to .env file
        if not env_path.exists():
            # Ensure directory exists before writing
            env_path.parent.mkdir(parents=True, exist_ok=True)
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("# PaperPal Environment Variables\n")

        set_key(str(env_path), "OPENAI_API_KEY", api_key)
        set_key(str(env_path), "OPENAI_BASE_URL", base_url)
        set_key(str(env_path), "OPENAI_MODEL", model)

        # Update current process environment
        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ["OPENAI_MODEL"] = model

        # Update config module variables
        config.OPENAI_API_KEY = api_key
        config.OPENAI_BASE_URL = base_url
        config.OPENAI_MODEL = model

        console.print(
            "[green]✅ Configuration saved to .env file! / 配置已保存至 .env 文件！[/green]\n"
        )


def main():
    """Main entry point"""
    # Check environment variables before anything else
    check_and_setup_env()

    parser = create_parser()
    args = parser.parse_args()

    cli = PaperResearchCLI()

    if args.command == "search":
        if args.mode:
            cli.search_mode = args.mode
            cli.preference_manager.set_search_mode(cli.search_mode)

        cli.run_once(
            time_range=args.time,
            topic=args.topic,
            show_all=args.all,
            threshold=args.threshold,
            save=not args.no_save,
            max_workers=args.max_workers,
        )
    elif args.command == "interactive":
        cli.run_interactive()
    elif args.command == "chat":
        if not cli.lang:
            cli.lang = "en"
        cli.run_chat_mode()
    elif args.command == "summary":
        if not cli.lang:
            cli.lang = "en"
        files = args.files if hasattr(args, "files") and args.files else None
        cli.generate_summary_for_files(files)
    elif args.command == "preferences":
        pref_manager = get_preference_manager()

        if args.show:
            console.print(
                Panel(pref_manager.get_preference_summary(), title="Preferences")
            )
        elif args.clear_history:
            pref_manager.clear_history()
            console.print("[green]History cleared[/green]")
        elif args.clear_all:
            if Confirm.ask("Clear all preferences?"):
                pref_manager.clear_all()
                console.print("[green]All preferences cleared[/green]")
        elif args.add_topic:
            pref_manager.add_interested_topic(args.add_topic)
            console.print(f"[green]Added: {args.add_topic}[/green]")
        elif args.add_not_topic:
            pref_manager.add_not_interested_topic(args.add_not_topic)
            console.print(
                f"[green]Added to not interested: {args.add_not_topic}[/green]"
            )
        elif args.set_custom:
            pref_manager.set_custom_preferences(args.set_custom)
            console.print("[green]Custom preferences set[/green]")
        elif args.set_lang:
            pref_manager.set_language(args.set_lang)
            console.print(f"[green]Language: {args.set_lang}[/green]")
        elif args.set_mode:
            pref_manager.set_search_mode(args.set_mode)
            console.print(f"[green]Search mode: {args.set_mode}[/green]")
        elif args.set_workers:
            pref_manager.set_max_workers(args.set_workers)
            console.print(f"[green]Max workers: {args.set_workers}[/green]")
        elif args.set_save:
            pref_manager.set_save_to_local(args.set_save == "on")
            console.print(f"[green]Save to local: {args.set_save}[/green]")
        elif args.set_output_dir:
            output_path = Path(args.set_output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            pref_manager.set_output_dir(str(output_path))
            console.print(f"[green]Output directory: {output_path}[/green]")
        elif args.set_save_results:
            pref_manager.set_save_results(args.set_save_results == "on")
            console.print(
                f"[green]Save results to file: {args.set_save_results}[/green]"
            )
        elif args.set_max_display:
            if args.set_max_display.lower() in ["unlimited", "none"]:
                pref_manager.set_max_display(None)
                console.print("[green]Max display papers: unlimited[/green]")
            else:
                try:
                    max_val = int(args.set_max_display)
                    pref_manager.set_max_display(max_val)
                    console.print(f"[green]Max display papers: {max_val}[/green]")
                except ValueError:
                    console.print("[red]Invalid number[/red]")
        elif args.set_auto_summary:
            pref_manager.set_auto_summary(args.set_auto_summary == "on")
            console.print(f"[green]Auto-summary: {args.set_auto_summary}[/green]")
        elif args.show_memory:
            memory = pref_manager.get_preference_context()
            if memory and memory.strip():
                console.print(
                    Panel(memory, title="🧠 Preference Memory", border_style="blue")
                )
            else:
                console.print(
                    "[dim]Memory is empty. The AI will learn your preferences as you provide feedback.[/dim]"
                )
        elif args.clear_memory:
            if Confirm.ask("Clear all preference memory?"):
                pref_manager.clear_memory()
                console.print("[green]Preference memory cleared[/green]")
        elif args.add_memory:
            pref_manager.add_preference_update(f"User preference: {args.add_memory}")
            # Use synchronous approach for CLI
            from src.llm_client import get_llm_client

            try:
                llm = get_llm_client()
                result = pref_manager._process_memory_update(llm)
                if result.get("status") == "success":
                    console.print("[green]Preference added to memory[/green]")
                else:
                    console.print("[green]Preference queued for update[/green]")
            except Exception:
                console.print("[green]Preference queued for update[/green]")
        else:
            console.print(
                Panel(pref_manager.get_preference_summary(), title="Preferences")
            )
    else:
        cli.run_interactive()


if __name__ == "__main__":
    main()
