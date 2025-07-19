# coding: utf-8

# =============================================================================
# ▼▼▼ このコード全体を一つの.pyファイルに保存して実行してください ▼▼▼
# =============================================================================

# =============================================================================
# ▼▼▼ 必要なライブラリのインストール ▼▼▼
# このコードを実行する前に、matplotlibをインストールする必要があります。
# ターミナルで以下のコマンドを実行してください:
# pip install matplotlib
# =============================================================================

from typing import List, Callable, Tuple
from datetime import date, datetime, timedelta
from collections import defaultdict
import calendar
import tkinter as tk
from tkinter import messagebox, font, ttk, simpledialog
import json
from pathlib import Path
import platform
import warnings
import math
import uuid

# Matplotlib関連のライブラリ
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib import font_manager
import matplotlib.animation as animation

# =============================================================================
# ▼▼▼ クロスプラットフォーム対応 日本語フォント自動設定 ▼▼▼
# =============================================================================
def set_optimal_font_for_matplotlib():
    font_name = None
    os_name = platform.system()
    if os_name == "Windows": font_candidates = ['Yu Gothic UI', 'Yu Gothic', 'Meiryo', 'MS Gothic']
    elif os_name == "Darwin": font_candidates = ['Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'System Font']
    else: font_candidates = ['Noto Sans CJK JP', 'IPAexGothic', 'VL Gothic']
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        for candidate in font_candidates:
            try:
                if font_manager.findfont(candidate, fallback_to_default=False):
                    font_name = candidate; break
            except: continue
    if font_name:
        plt.rcParams['font.family'] = font_name
        if os_name == "Darwin": plt.rcParams['font.sans-serif'] = [font_name, 'DejaVu Sans']
        else: plt.rcParams['font.sans-serif'] = [font_name]
    else:
        plt.rcParams['font.family'] = 'sans-serif'
        print("WARN: Preferred Japanese fonts not found. Falling back to default 'sans-serif'.")
        print("      Consider installing one of: " + ", ".join(font_candidates))
set_optimal_font_for_matplotlib()
# =============================================================================

# =============================================================================
# 0. ユーティリティクラス
# =============================================================================
class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip); self.widget.bind("<Leave>", self.hide_tooltip)
    def bind_widget(self, child_widget):
        child_widget.bind("<Enter>", self.show_tooltip); child_widget.bind("<Leave>", self.hide_tooltip)
    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text: return
        x, y, _, _ = self.widget.bbox("insert"); x += self.widget.winfo_rootx() + 25; y += self.widget.winfo_rooty() + 25
        self.tooltip_window = tw = tk.Toplevel(self.widget); tw.wm_overrideredirect(True); tw.wm_geometry(f"+{x}+{y}")
        tooltip_font_family = font.nametofont("TkDefaultFont").cget("family")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT, background="#ffffe0", relief=tk.SOLID, borderwidth=1, font=(tooltip_font_family, 9, "normal"))
        label.pack(ipadx=5, ipady=3)
    def hide_tooltip(self, event=None):
        if self.tooltip_window: self.tooltip_window.destroy()
        self.tooltip_window = None

class SettingsManager:
    def __init__(self, filename="app_settings.json"):
        self.filepath = Path.home() / ".simple_kakeibo" / filename; self.filepath.parent.mkdir(parents=True, exist_ok=True)
        # [MODIFIED] 収入カテゴリのデフォルト色もPCCSベースに更新
        self.defaults = {
            "app_theme": "default_light_gray",
            "expense_colors": {
                "食費": "#f3581f", "交通費": "#fca500", "家賃": "#007d9f",
                "娯楽": "#d7003a", "日用品": "#a3d638", "交際費": "#c5398a", "その他": "#7f7f7f"
            },
            "income_colors": {
                "給与": "#00a95f", "賞与": "#fde800", "副業": "#0f59a4",
                "臨時収入": "#f8981d", "その他": "#9e9e9e"
            }
        }
        self.settings = self._load()
    def _load(self):
        try:
            with self.filepath.open('r', encoding='utf-8') as f:
                loaded_settings = json.load(f)
                for key, value in self.defaults.items(): loaded_settings.setdefault(key, value)
                return loaded_settings
        except (FileNotFoundError, json.JSONDecodeError): return self.defaults.copy()
    def get(self, key): return self.settings.get(key, self.defaults.get(key))
    def set(self, key, value): self.settings[key] = value; self._save()
    def _save(self):
        with self.filepath.open('w', encoding='utf-8') as f: json.dump(self.settings, f, indent=4)
        
    def get_colors(self, type: str) -> dict:
        key = f"{type}_colors"
        colors = self.defaults[key].copy()
        colors.update(self.settings.get(key, {}))
        return colors

    def set_color(self, type: str, category: str, color: str):
        key = f"{type}_colors"
        if key not in self.settings:
            self.settings[key] = self.defaults[key].copy()
        self.settings[key][category] = color
        self._save()

    def reset_colors(self, type: str):
        key = f"{type}_colors"
        self.settings[key] = self.defaults[key].copy()
        self._save()

# =============================================================================

# =============================================================================
# 1. モデル (Model)
# =============================================================================
class Transaction:
    def __init__(self, amount: int, category: str, transaction_date: date, type: str, id: str = None):
        if not isinstance(amount, int) or amount <= 0: raise ValueError("金額は正の整数で入力してください。")
        if not category or not category.strip(): raise ValueError("カテゴリは空にできません。")
        if not isinstance(transaction_date, date): raise ValueError("日付は有効な日付オブジェクトである必要があります。")
        if type not in ['income', 'expense']: raise ValueError("取引種別は 'income' または 'expense' である必要があります。")
        
        self.id = id if id is not None else str(uuid.uuid4())
        self.amount = amount; self.category = category.strip(); self.transaction_date = transaction_date; self.type = type
        
    def to_card_data(self) -> dict:
        sign = "+" if self.type == 'income' else "-"; return {"date_str": f"{self.transaction_date.month}月{self.transaction_date.day}日", "category": self.category, "amount_str": f"{sign}¥{self.amount:,}", "type": self.type}
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "amount": self.amount,
            "category": self.category,
            "transaction_date": self.transaction_date.isoformat(),
            "type": self.type
        }

    @staticmethod
    def from_dict(data: dict) -> 'Transaction':
        return Transaction(
            id=data["id"],
            amount=data["amount"],
            category=data["category"],
            transaction_date=date.fromisoformat(data["transaction_date"]),
            type=data["type"]
        )

class Ledger:
    def __init__(self):
        self.filepath = Path.home() / ".simple_kakeibo" / "transactions.json"
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._transactions: List[Transaction] = self._load()

    def _load(self) -> List[Transaction]:
        try:
            with self.filepath.open('r', encoding='utf-8') as f:
                raw_data = json.load(f)
                return [Transaction.from_dict(item) for item in raw_data]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        with self.filepath.open('w', encoding='utf-8') as f:
            data_to_save = [tx.to_dict() for tx in self._transactions]
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
            
    def add_transaction(self, transaction: Transaction):
        self._transactions.append(transaction)
        self._transactions.sort(key=lambda x: x.transaction_date, reverse=True)
        self._save()

    def get_all_transactions(self) -> List[Transaction]: return self._transactions
    def get_expense_summary_for_month(self, year: int, month: int) -> int: return sum(tx.amount for tx in self._transactions if tx.transaction_date.year == year and tx.transaction_date.month == month and tx.type == 'expense')
    def get_income_summary_for_month(self, year: int, month: int) -> int: return sum(tx.amount for tx in self._transactions if tx.transaction_date.year == year and tx.transaction_date.month == month and tx.type == 'income')
    def get_category_summary_for_month(self, year: int, month: int) -> dict[str, int]:
        category_summary = defaultdict(int)
        for tx in self._transactions:
            if tx.transaction_date.year == year and tx.transaction_date.month == month and tx.type == 'expense': category_summary[tx.category] += tx.amount
        return dict(sorted(category_summary.items(), key=lambda item: item[1], reverse=True))
    def get_income_category_summary_for_month(self, year: int, month: int) -> dict[str, int]:
        category_summary = defaultdict(int)
        for tx in self._transactions:
            if tx.transaction_date.year == year and tx.transaction_date.month == month and tx.type == 'income': category_summary[tx.category] += tx.amount
        return dict(sorted(category_summary.items(), key=lambda item: item[1], reverse=True))
    def get_transactions_for_day(self, target_date: date) -> List[Transaction]: return [tx for tx in self._transactions if tx.transaction_date == target_date]
    
    def delete_transactions_for_day(self, target_date: date) -> int:
        initial_count = len(self._transactions)
        self._transactions = [tx for tx in self._transactions if tx.transaction_date != target_date]
        num_deleted = initial_count - len(self._transactions)
        if num_deleted > 0:
            self._save()
        return num_deleted
# =============================================================================

# =============================================================================
# 1.5. Todoモデル
# =============================================================================
class TodoItem:
    def __init__(self, content: str, due_date: date, is_completed: bool = False, id: str = None):
        if not content or not content.strip(): raise ValueError("内容は空にできません。")
        self.id = id if id is not None else str(uuid.uuid4())
        self.content = content.strip(); self.due_date = due_date; self.is_completed = is_completed
    def to_dict(self): return {"id": self.id, "content": self.content, "due_date": self.due_date.isoformat(), "is_completed": self.is_completed}
    @staticmethod
    def from_dict(data: dict): return TodoItem(id=data["id"], content=data["content"], due_date=date.fromisoformat(data["due_date"]), is_completed=data["is_completed"])

class TodoManager:
    def __init__(self, filename="todos.json"):
        self.filepath = Path.home() / ".simple_kakeibo" / filename; self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self.todos: List[TodoItem] = self._load()
    def _load(self) -> List[TodoItem]:
        try:
            with self.filepath.open('r', encoding='utf-8') as f: return [TodoItem.from_dict(item) for item in json.load(f)]
        except (FileNotFoundError, json.JSONDecodeError): return []
    def _save(self):
        with self.filepath.open('w', encoding='utf-8') as f: json.dump([item.to_dict() for item in self.todos], f, indent=4, ensure_ascii=False)
    def add_todo(self, content: str, due_date: date) -> TodoItem:
        new_todo = TodoItem(content=content, due_date=due_date); self.todos.append(new_todo); self.todos.sort(key=lambda t: t.due_date, reverse=True); self._save(); return new_todo
    def get_all_todos(self) -> List[TodoItem]: return sorted(self.todos, key=lambda t: (t.due_date, t.is_completed), reverse=False)
    def get_uncompleted_todos_for_day(self, target_date: date) -> List[TodoItem]: return [t for t in self.todos if t.due_date == target_date and not t.is_completed]
    def update_todo_status(self, todo_id: str, is_completed: bool):
        todo = next((t for t in self.todos if t.id == todo_id), None)
        if todo: todo.is_completed = is_completed; self._save()
    def delete_todo(self, todo_id: str):
        initial_len = len(self.todos); self.todos = [t for t in self.todos if t.id != todo_id]
        if len(self.todos) < initial_len: self._save()
# =============================================================================


# =============================================================================
# 2. ビュー(View) & コントローラ(Controller)
# =============================================================================

PCCS_COLORS = [
    ("pR 紫みの赤", "#d7003a"), ("R 赤", "#e60012"), ("yR 黄みの赤", "#f3581f"),
    ("rO 赤みのだいだい", "#f8981d"), ("O だいだい", "#fca500"), ("yO 黄みのだいだい", "#fdb813"),
    ("rY 赤みの黄", "#fdd000"), ("Y 黄", "#fde800"), ("gY 緑みの黄", "#d9e021"),
    ("YG 黄緑", "#a3d638"), ("yG 黄みの緑", "#69c04b"), ("G 緑", "#00a95f"),
    ("bG 青みの緑", "#009e73"), ("BG 青緑", "#009b95"), ("gB 緑みの青", "#008eab"),
    ("B 青", "#007d9f"), ("pB 紫みの青", "#006aa8"), ("V 青紫", "#0f59a4"),
    ("bP 青みの紫", "#645da9"), ("P 紫", "#884897"), ("rP 赤みの紫", "#a94395"),
    ("RP 赤紫", "#c5398a"), ("pRP 紫みの赤紫", "#d6327b"), ("R-P 赤紫（赤寄り）", "#d50065")
]
GRAY_COLORS = [
    ("ライトグレー", "#cccccc"), ("グレー", "#9e9e9e"), ("ダークグレー", "#7f7f7f")
]

class PccsColorPickerDialog(tk.Toplevel):
    def __init__(self, parent, title, current_colors, on_select_callback):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        self.current_used_colors = set(c.lower() for c in current_colors.values())
        self.on_select_callback = on_select_callback
        
        self._create_widgets()

    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        ttk.Label(main_frame, text="カラーパレット").pack(anchor="w")
        pccs_frame = ttk.Frame(main_frame)
        pccs_frame.pack(fill=tk.X, pady=(2, 10))
        self._populate_color_grid(pccs_frame, PCCS_COLORS, 6)
        
        ttk.Separator(main_frame).pack(fill=tk.X, pady=5)

        ttk.Label(main_frame, text="無彩色").pack(anchor="w")
        gray_frame = ttk.Frame(main_frame)
        gray_frame.pack(fill=tk.X, pady=2)
        self._populate_color_grid(gray_frame, GRAY_COLORS, 6)

    def _populate_color_grid(self, parent_frame, colors, columns):
        for index, (color_name, color_hex) in enumerate(colors):
            row = index // columns
            col = index % columns
            
            color_box = tk.Label(parent_frame, text="", background=color_hex, width=6, height=2, relief="raised", borderwidth=2)
            color_box.grid(row=row, column=col, padx=4, pady=4)
            
            is_used = color_hex.lower() in self.current_used_colors
            
            if is_used:
                color_box.config(relief="flat", borderwidth=1)
                Tooltip(color_box, "他のカテゴリで使用中")
            else:
                color_box.config(cursor="hand2")
                color_box.bind("<Button-1>", lambda e, c=color_hex: self._on_color_selected(c))
                Tooltip(color_box, color_name)
    
    def _on_color_selected(self, selected_color_hex):
        if self.on_select_callback:
            self.on_select_callback(selected_color_hex)
        self.destroy()

class SettingsView(ttk.Frame):
    THEMES = {
        "デフォルト (ライトグレー)": "default_light_gray",
        "パステルミント": "pastel_mint",
        "ソフトラベンダー": "soft_lavender",
    }
    def __init__(self, parent: tk.Tk, settings_manager: SettingsManager, on_settings_change_callback: Callable):
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.on_settings_change = on_settings_change_callback

        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, padding=20)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.scrollable_frame.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        
        self.selected_theme = tk.StringVar(value=self.settings_manager.get("app_theme"))

        theme_labelframe = ttk.LabelFrame(self.scrollable_frame, text="アプリケーションテーマ")
        theme_labelframe.pack(fill=tk.X, pady=10)
        for name, theme_key in self.THEMES.items():
            ttk.Radiobutton(theme_labelframe, text=name, variable=self.selected_theme, value=theme_key, command=self._apply_theme, style="Theme.TRadiobutton").pack(anchor="w", padx=20, pady=2)
            
        self._create_color_settings_ui(self.scrollable_frame)

    def _on_mousewheel(self, event):
        if not (self.winfo_ismapped() and self.winfo_containing(event.x_root, event.y_root) == self.canvas):
            return

        if platform.system() == "Windows":
            scroll_units = -1 * (event.delta // 120)
        elif platform.system() == "Darwin":
            scroll_units = event.delta
        else:
            scroll_units = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(scroll_units, "units")

    def _apply_theme(self):
        theme_key = self.selected_theme.get()
        self.settings_manager.set("app_theme", theme_key)
        self.on_settings_change()

    def _create_color_settings_ui(self, parent_frame):
        colors_labelframe = ttk.LabelFrame(parent_frame, text="グラフの色設定")
        colors_labelframe.pack(fill=tk.X, pady=10, ipady=5)

        self.color_section_frames = {}
        
        expense_frame = self._build_category_color_section(colors_labelframe, "expense", "支出カテゴリ")
        self.color_section_frames["expense"] = expense_frame

        income_frame = self._build_category_color_section(colors_labelframe, "income", "収入カテゴリ")
        self.color_section_frames["income"] = income_frame

    def _build_category_color_section(self, parent, type, title):
        section_frame = ttk.Frame(parent, padding=5)
        section_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
        
        header_frame = ttk.Frame(section_frame)
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text=title, font=("", 10, "bold")).pack(anchor="w", side=tk.LEFT)

        colors_container = ttk.Frame(section_frame)
        colors_container.pack(fill=tk.X)
        
        colors = self.settings_manager.get_colors(type)
        categories = AddTransactionWindow.EXPENSE_CATEGORIES if type == 'expense' else AddTransactionWindow.INCOME_CATEGORIES
        
        for category in categories:
            color = colors.get(category)
            item_frame = ttk.Frame(colors_container)
            item_frame.pack(fill=tk.X, padx=15, pady=2)
            
            color_box = tk.Label(item_frame, text=" ", bg=color, width=3, relief="sunken", borderwidth=1)
            color_box.pack(side=tk.LEFT, padx=(0, 10))
            
            ttk.Label(item_frame, text=category, width=8).pack(side=tk.LEFT, expand=True, anchor="w")
            
            change_button = ttk.Button(item_frame, text="変更", 
                                       command=lambda t=type, cat=category, box=color_box: self._handle_color_change(t, cat, box))
            change_button.pack(side=tk.RIGHT)

        reset_button = ttk.Button(section_frame, text=f"デフォルトに戻す", style="Toolbutton.TButton",
                                  command=lambda t=type: self._handle_reset_colors(t))
        reset_button.pack(pady=5, anchor="e", padx=5)
        return section_frame

    def _handle_color_change(self, type: str, category: str, color_box: tk.Label):
        current_colors = self.settings_manager.get_colors(type)
        other_colors = {k: v for k, v in current_colors.items() if k != category}

        def on_dialog_select(new_hex_color: str):
            if new_hex_color:
                self.settings_manager.set_color(type, category, new_hex_color)
                color_box.config(bg=new_hex_color)
                self.on_settings_change()

        dialog_title = f"「{category}」の色を選択"
        PccsColorPickerDialog(
            parent=self, 
            title=dialog_title,
            current_colors=other_colors, 
            on_select_callback=on_dialog_select
        )

    def _handle_reset_colors(self, type):
        title_text = '支出カテゴリ' if type == 'expense' else '収入カテゴリ'
        if messagebox.askyesno("確認", f"{title_text}の色を全てデフォルトに戻しますか？", parent=self):
            self.settings_manager.reset_colors(type)
            
            for child in self.scrollable_frame.winfo_children():
                if isinstance(child, ttk.LabelFrame) and "グラフの色設定" in child.cget("text"):
                    for section in child.winfo_children():
                        section.destroy()
                    self.color_section_frames["expense"] = self._build_category_color_section(child, "expense", "支出カテゴリ")
                    self.color_section_frames["income"] = self._build_category_color_section(child, "income", "収入カテゴリ")
                    break
            self.on_settings_change()

class AddTransactionWindow(tk.Toplevel):
    EXPENSE_CATEGORIES = ["食費", "交通費", "家賃", "娯楽", "日用品", "交際費", "その他"]; INCOME_CATEGORIES = ["給与", "賞与", "副業", "臨時収入", "その他"]
    def __init__(self, parent: tk.Tk, ledger: Ledger, on_close_callback: Callable[[Transaction], None], initial_date: date = None):
        super().__init__(parent); self.ledger = ledger; self.on_close_callback = on_close_callback; self.initial_date = initial_date if initial_date is not None else date.today()
        self.title("取引の追加"); self.geometry("400x250"); self.resizable(False, False); self.transient(parent); self.grab_set(); self._create_widgets()
    
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=(20, 10)); main_frame.pack(fill=tk.BOTH, expand=True); main_frame.columnconfigure(1, weight=1)
        
        self.transaction_type = tk.StringVar(value="expense")
        ttk.Label(main_frame, text="取引種別:").grid(row=0, column=0, sticky="w", pady=5)
        type_frame = ttk.Frame(main_frame); type_frame.grid(row=0, column=1, sticky="ew", pady=(0, 10))
        
        expense_btn = ttk.Radiobutton(type_frame, text="支出", variable=self.transaction_type, value="expense", command=self._update_categories, style="Type.TRadiobutton")
        expense_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        income_btn = ttk.Radiobutton(type_frame, text="収入", variable=self.transaction_type, value="income", command=self._update_categories, style="Type.TRadiobutton")
        income_btn.pack(side=tk.LEFT, expand=True, fill=tk.X)

        ttk.Label(main_frame, text="日付:").grid(row=1, column=0, sticky="w", pady=5)
        date_display_label = ttk.Label(main_frame, text=self.initial_date.strftime('%Y-%m-%d'))
        date_display_label.grid(row=1, column=1, sticky="ew", padx=5)

        ttk.Label(main_frame, text="金額:").grid(row=2, column=0, sticky="w", pady=5)
        self.amount_entry = ttk.Entry(main_frame); self.amount_entry.grid(row=2, column=1, sticky="ew", padx=5); self.amount_entry.focus_set()
        
        ttk.Label(main_frame, text="カテゴリ:").grid(row=3, column=0, sticky="w", pady=5)
        self.category_combobox = ttk.Combobox(main_frame, state="readonly"); self.category_combobox.grid(row=3, column=1, sticky="ew", padx=5); self._update_categories()
        
        button_frame = ttk.Frame(main_frame); button_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        save_button = tk.Button(button_frame,
                                text="保存",
                                command=self._handle_save,
                                font=(font.nametofont("TkDefaultFont").cget("family"), 12, "bold"),
                                foreground="#ffffff",
                                background="#000000",
                                activebackground="#333333",
                                activeforeground="#ffffff",
                                relief=tk.FLAT,
                                borderwidth=0,
                                padx=20,
                                pady=5)
        save_button.pack()
    
    def _update_categories(self):
        type_selected = self.transaction_type.get(); self.category_combobox['values'] = self.EXPENSE_CATEGORIES if type_selected == "expense" else self.INCOME_CATEGORIES; self.category_combobox.current(0)
    
    def _handle_save(self):
        try:
            selected_date = self.initial_date
            amount = int(self.amount_entry.get())
            new_tx = Transaction(amount, self.category_combobox.get(), selected_date, self.transaction_type.get())
            self.ledger.add_transaction(new_tx)
            self.on_close_callback(new_tx)
            self.destroy()
        except (ValueError, TypeError) as e: messagebox.showerror("入力エラー", str(e), parent=self)
        except Exception as e: messagebox.showerror("予期せぬエラー", f"エラーが発生しました: {e}", parent=self)

class AddTodoWindow(tk.Toplevel):
    def __init__(self, parent: tk.Tk, todo_manager: TodoManager, on_close_callback: Callable, initial_date: date = None):
        super().__init__(parent); self.todo_manager = todo_manager; self.on_close_callback = on_close_callback; self.initial_date = initial_date or date.today()
        self.title("Todoの追加"); self.geometry("400x180"); self.resizable(False, False); self.transient(parent); self.grab_set(); self._create_widgets()
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=(20, 10)); main_frame.pack(fill=tk.BOTH, expand=True); main_frame.columnconfigure(1, weight=1)
        ttk.Label(main_frame, text="日付 (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", pady=5)
        self.date_entry = ttk.Entry(main_frame); self.date_entry.insert(0, self.initial_date.strftime('%Y-%m-%d')); self.date_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(main_frame, text="内容:").grid(row=1, column=0, sticky="w", pady=5)
        self.content_entry = ttk.Entry(main_frame); self.content_entry.grid(row=1, column=1, sticky="ew", padx=5); self.content_entry.focus_set()
        button_frame = ttk.Frame(main_frame); button_frame.grid(row=2, column=0, columnspan=2, pady=20)

        save_button = tk.Button(button_frame,
                                text="保存",
                                command=self._handle_save,
                                font=(font.nametofont("TkDefaultFont").cget("family"), 12, "bold"),
                                foreground="#ffffff",
                                background="#000000",
                                activebackground="#333333",
                                activeforeground="#ffffff",
                                relief=tk.FLAT,
                                borderwidth=0,
                                padx=20,
                                pady=5)
        save_button.pack()

    def _handle_save(self):
        try:
            target_date = datetime.strptime(self.date_entry.get(), '%Y-%m-%d').date(); content = self.content_entry.get()
            self.todo_manager.add_todo(content, target_date)
            self.on_close_callback(); self.destroy()
        except ValueError as e: messagebox.showerror("入力エラー", str(e), parent=self)
        except Exception as e: messagebox.showerror("予期せぬエラー", f"エラーが発生しました: {e}", parent=self)

class ChartView(ttk.Frame):
    BALANCE_COLORS = {"収入": "#4caf50", "支出": "#d62728"}; DEFAULT_COLOR = "#cccccc"
    def __init__(self, parent, chart_type: str, settings_manager: SettingsManager, **kwargs):
        super().__init__(parent, **kwargs)
        self.settings_manager = settings_manager
        self.chart_type = chart_type; self.font_family = plt.rcParams['font.family']; self.fig = Figure(figsize=(3.5, 4), dpi=100, constrained_layout=True); self.fig.patch.set_facecolor('#ffffff')
        self.ax = self.fig.add_subplot(111); self.canvas = FigureCanvasTkAgg(self.fig, master=self); self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True); self.last_rendered_period = None; self.anim_job = None; self.anim_params = {}
    
    def update_chart(self, year: int, month: int, data: dict, balance_data: dict):
        if self.anim_job: self.after_cancel(self.anim_job); self.anim_job = None
        self.anim_params = {}; self.ax.clear();
        if self.fig.legends: self.fig.legends.clear()
        
        has_data = False
        summary_data, total_value, labels, colors = {}, 0, [], []
        if self.chart_type in ['expense', 'income']:
            if data and sum(data.values()) > 0:
                has_data = True
                summary_data = data
                total_value = sum(summary_data.values())
                labels = list(summary_data.keys())
                color_map = self.settings_manager.get_colors(self.chart_type)
                colors = [color_map.get(label, self.DEFAULT_COLOR) for label in labels]
        elif self.chart_type == 'balance':
            if balance_data and (balance_data.get('収入', 0) > 0 or balance_data.get('支出', 0) > 0):
                has_data = True
                summary_data = {k: v for k, v in balance_data.items() if v > 0}
                total_value = balance_data.get('収入', 0) - balance_data.get('支出', 0)
                labels = list(summary_data.keys())
                colors = [self.BALANCE_COLORS.get(label) for label in labels]
        
        if not has_data:
            msg = f"{year}年{month}月の{ {'expense':'支出', 'income':'収入', 'balance':'取引'}[self.chart_type] }データはありません"
            self.ax.text(0.5, 0.5, msg, ha='center', va='center', fontfamily=self.font_family)
            self.ax.axis('off') 
            self.canvas.draw_idle()
            return
            
        self.last_rendered_period = (year, month)
        self.total_frames = 30; self.animation_duration = 0.25; interval_ms = self.animation_duration / self.total_frames; 
        self.anim_params = {"data": summary_data, "colors": colors, "labels": labels, "total_value": total_value, "current_frame": 0, "interval_ms": int(max(1, interval_ms * 1000))}
        self._run_animation()

    def _run_animation(self):
        params = self.anim_params; current_frame = params.get("current_frame", 0); self._animate(current_frame); params["current_frame"] = current_frame + 1
        if params["current_frame"] <= self.total_frames: self.anim_job = self.after(params["interval_ms"], self._run_animation)
        else: self.anim_job = None
    def _ease_in_out(self, progress: float) -> float: return 0.5 * (1 - math.cos(progress * math.pi))
    
    def _animate(self, frame):
        params = self.anim_params; data, colors = params.get("data", {}), params.get("colors", []);
        if not data: return
        progress = self._ease_in_out(frame / self.total_frames) if self.total_frames > 0 else 1.0; self.ax.clear(); self.ax.axis('equal'); sizes = list(data.values())
        if not sizes: return
        self.ax.pie([s * progress for s in sizes] + [sum(sizes) * (1 - progress)], startangle=90, counterclock=False, colors=colors + ['#00000000'], wedgeprops=dict(width=0.4, edgecolor='w'))
        self.canvas.draw_idle()
        if frame >= self.total_frames: self._draw_final_details(params.get("data"), params.get("colors"), params.get("labels"), params.get("total_value"))
    
    def _draw_final_details(self, data, colors, labels, total_value):
        self.ax.clear(); self.ax.axis('equal'); 
        if not data: return
        
        INCOME_COLOR = "#007aff"
        EXPENSE_COLOR = "#d62728"

        sizes = list(data.values())
        if not sizes or sum(sizes) == 0: return

        wedges, _ = self.ax.pie(sizes, autopct=None, startangle=90, counterclock=False, colors=colors, wedgeprops=dict(width=0.4, edgecolor='w'))
        
        text, color = "", "black"
        if self.chart_type == 'expense': 
            text, color = f"支出合計\n-¥{sum(sizes):,}", EXPENSE_COLOR
        elif self.chart_type == 'income': 
            text, color = f"収入合計\n+¥{sum(sizes):,}", INCOME_COLOR
        elif self.chart_type == 'balance': 
            sign = "+" if total_value >= 0 else "-"
            color = INCOME_COLOR if total_value >= 0 else EXPENSE_COLOR
            text = f"収支\n{sign}¥{abs(total_value):,}"
        
        self.ax.text(0, 0, text, ha='center', va='center', size=12, weight='bold', color=color, fontfamily=self.font_family)
        if self.chart_type != 'balance': self.fig.legend(wedges, labels, loc="center right", bbox_to_anchor=(0.99, 0.5), prop={'family': self.font_family, 'size': 9})
        self.canvas.draw_idle()

class TodoView(ttk.Frame):
    def __init__(self, parent, todo_manager: TodoManager, on_change_callback: Callable):
        super().__init__(parent); self.todo_manager = todo_manager; self.on_change = on_change_callback; self.add_todo_window = None
        self._create_widgets()

    def _create_widgets(self):
        header = ttk.Frame(self); header.pack(fill=tk.X, pady=(10, 15))
        add_button = ttk.Button(header, text="+ タスクを追加する", command=self._open_add_dialog, style="LargeAdd.TButton")
        add_button.pack()
        self.canvas = tk.Canvas(self, bg="#ffffff", highlightthickness=0); scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.list_frame = ttk.Frame(self.canvas, style="Content.TFrame"); self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.list_frame, anchor="nw"); self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True); scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.list_frame.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event):
        if not (self.winfo_ismapped() and self.winfo_containing(event.x_root, event.y_root) == self.canvas):
            return
            
        if platform.system() == "Windows":
            scroll_units = -1 * (event.delta // 120)
        elif platform.system() == "Darwin":
             scroll_units = event.delta
        else:
            scroll_units = -1 if event.delta > 0 else 1
        self.canvas.yview_scroll(scroll_units, "units")
    
    def _bind_mousewheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_mousewheel)
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child)

    def update_list(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        all_todos = self.todo_manager.get_all_todos()
        if not all_todos: ttk.Label(self.list_frame, text="タスクはありません", font=("", 10, "italic"), style="Content.TLabel").pack(pady=20); return
        
        grouped_by_day = defaultdict(list)
        for todo in all_todos: grouped_by_day[todo.due_date].append(todo)
        
        for day, todos_in_day in sorted(grouped_by_day.items()):
            self._create_day_header(day); [self._create_todo_card(todo) for todo in todos_in_day]
        
        self._bind_mousewheel_recursive(self.list_frame)


    def _create_day_header(self, day: date):
        day_header_frame = ttk.Frame(self.list_frame, padding=(0, 5), style="Header.TFrame")
        day_header_frame.pack(fill=tk.X, padx=5, pady=(8, 2))
        ttk.Label(day_header_frame, text=f"{day.day}日 ({'月火水木金土日'[day.weekday()]})", font=("", 10, "bold"), style="Header.TLabel").pack(side=tk.LEFT)
    def _create_todo_card(self, todo: TodoItem):
        card_frame = ttk.Frame(self.list_frame, padding=5, style="Content.TFrame"); card_frame.pack(fill=tk.X, padx=10, pady=1); card_frame.columnconfigure(1, weight=1)
        check_var = tk.BooleanVar(value=todo.is_completed)
        check = ttk.Checkbutton(card_frame, variable=check_var, command=lambda: self._toggle_complete(todo.id, check_var), style="Content.TCheckbutton")
        check.grid(row=0, column=0)
        
        label_font = font.Font(family=font.nametofont("TkDefaultFont").cget("family"), size=10)
        if todo.is_completed: label_font.configure(overstrike=True)
        label = ttk.Label(card_frame, text=todo.content, font=label_font, style="Content.TLabel", anchor="w"); label.grid(row=0, column=1, sticky="ew", padx=5)
        
        delete_button = ttk.Button(card_frame, text="🗑️", width=3, style="Toolbutton.TButton", command=lambda: self._handle_delete(todo.id)); delete_button.grid(row=0, column=2)
    def _toggle_complete(self, todo_id: str, var: tk.BooleanVar):
        self.todo_manager.update_todo_status(todo_id, var.get()); self.update_list(); self.on_change()
    def _handle_delete(self, todo_id: str):
        if messagebox.askyesno("削除の確認", "このタスクを削除しますか？", parent=self):
            self.todo_manager.delete_todo(todo_id); self.update_list(); self.on_change()
    def _open_add_dialog(self):
        if self.add_todo_window is None or not self.add_todo_window.winfo_exists():
            self.add_todo_window = AddTodoWindow(self, self.todo_manager, lambda: (self.update_list(), self.on_change()))
        else: self.add_todo_window.lift()

class CalendarView(ttk.Frame):
    def __init__(self, parent, *, style: ttk.Style, ledger: Ledger, todo_manager: TodoManager, on_date_click_callback: Callable[[date], None], on_month_change_callback: Callable[[date], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.style = style
        self.ledger = ledger
        self.todo_manager = todo_manager
        self.on_date_click_callback = on_date_click_callback; self.on_month_change_callback = on_month_change_callback
        self.current_date = date.today(); self._font_measurer_label = ttk.Label(self); self._create_widgets()
        # 【修正】初期化時の直接描画を削除。描画は親コンポーネントの準備ができてから呼び出される。
        # self.render_calendar() 
    
    def _create_widgets(self):
        header_frame = ttk.Frame(self); header_frame.pack(fill=tk.X, pady=5, padx=5); header_frame.columnconfigure(1, weight=1)
        ttk.Button(header_frame, text="< 前月", command=self.go_to_prev_month).grid(row=0, column=0, sticky="w")
        self.month_label = ttk.Label(header_frame, text="", font=("", 14, "bold"), anchor="center"); self.month_label.grid(row=0, column=1, sticky="ew")
        ttk.Button(header_frame, text="次月 >", command=self.go_to_next_month).grid(row=0, column=2, sticky="e")
        self.calendar_grid = ttk.Frame(self, style="Grid.TFrame"); self.calendar_grid.pack(fill=tk.BOTH, expand=True)

        self.calendar_grid.rowconfigure(0, weight=0)
        for i in range(1, 7): self.calendar_grid.rowconfigure(i, weight=1)
        for i in range(7): self.calendar_grid.columnconfigure(i, weight=1)

    def _get_truncated_text(self, text: str, font_config: tuple, max_width: int) -> Tuple[str, bool]:
        self._font_measurer_label.config(font=font_config)
        measured_width = self._font_measurer_label.tk.call("font", "measure", self._font_measurer_label.cget("font"), text)
        if measured_width <= max_width:
            return text, False
        for i in range(len(text) - 1, 0, -1):
            truncated = text[:i] + "…";
            measured_width = self._font_measurer_label.tk.call("font", "measure", self._font_measurer_label.cget("font"), truncated)
            if measured_width <= max_width:
                return truncated, True
        return "…", True
    
    def render_calendar(self):
        # セルの横幅計算が、ウィジェットのサイズが確定してから行われるようにする
        if self.calendar_grid.winfo_width() <= 1:
            # まだサイズが確定していない場合は、少し待ってから再試行
            self.after(50, self.render_calendar)
            return

        for widget in self.calendar_grid.winfo_children(): widget.destroy()
        year, month = self.current_date.year, self.current_date.month; self.month_label.config(text=f"{year}年 {month}月")
        weekdays = ["日", "月", "火", "水", "木", "金", "土"]

        INCOME_COLOR = "#007aff"
        EXPENSE_COLOR = "#d62728"
        DEFAULT_COLOR = "#000000"
        WEEKDAY_HEADER_BG = "#e8e8e8"

        for i, day_name in enumerate(weekdays):
            color = EXPENSE_COLOR if day_name == "日" else INCOME_COLOR if day_name == "土" else DEFAULT_COLOR
            d_label_frame = ttk.Frame(self.calendar_grid, style="WeekdayHeader.TFrame"); d_label_frame.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
            label = ttk.Label(d_label_frame, text=day_name, anchor="center", foreground=color, font=("", 9, "bold"), background=WEEKDAY_HEADER_BG)
            label.pack(expand=True, fill="both", ipady=2)
        
        month_days = calendar.monthcalendar(year, month)
        cell_width = self.calendar_grid.winfo_width() / 7 - 10
        for week_index, week in enumerate(month_days):
            for day_index, day in enumerate(week):
                if day == 0: continue
                date_obj = date(year, month, day)
                day_cell = ttk.Frame(self.calendar_grid, style="CalendarDay.TFrame"); day_cell.grid(row=week_index + 1, column=day_index, sticky="nsew", padx=1, pady=1)
                day_cell.grid_propagate(False); day_cell.rowconfigure(1, weight=1); day_cell.columnconfigure(0, weight=1)
                header_frame = ttk.Frame(day_cell, style="Content.TFrame"); header_frame.grid(row=0, column=0, sticky="ew")
                content_frame = ttk.Frame(day_cell, style="Content.TFrame"); content_frame.grid(row=1, column=0, sticky="nsew")

                date_canvas = tk.Canvas(header_frame, width=30, height=30, highlightthickness=0)
                date_canvas.configure(bg=self.style.lookup("Content.TFrame", "background"))
                date_canvas.pack(side=tk.LEFT, padx=4, pady=2)
                
                if date_obj == date.today():
                    accent_color = self.style.lookup("Nav.TRadiobutton", "foreground", ("selected",))
                    date_canvas.create_oval(2, 2, 28, 28, outline=accent_color, width=2)

                date_canvas.create_text(15, 15, text=str(day), font=("", 12), fill=DEFAULT_COLOR)
                
                uncompleted_todos = self.todo_manager.get_uncompleted_todos_for_day(date_obj)
                if uncompleted_todos:
                    num_todos = len(uncompleted_todos)
                    task_display_text = f"💬({num_todos})"
                    todo_icon_label = ttk.Label(header_frame, text=task_display_text, foreground="#007aff", style="Content.TLabel"); todo_icon_label.pack(side=tk.LEFT, padx=(0, 2))
                    todo_tooltip_text = "【タスク一覧】\n" + "\n".join(f"・{t.content}" for t in uncompleted_todos)
                    Tooltip(todo_icon_label, todo_tooltip_text)

                day_transactions = self.ledger.get_transactions_for_day(date_obj)
                if day_transactions:
                    category_frame = ttk.Frame(content_frame, style="Indicator.TFrame"); category_frame.pack(fill=tk.X, padx=2, pady=(2, 0))
                    income_by_cat = defaultdict(int); expense_by_cat = defaultdict(int)
                    for tx in day_transactions:
                        if tx.type == 'income': income_by_cat[tx.category] += tx.amount
                        else: expense_by_cat[tx.category] += tx.amount
                    
                    was_truncated = False
                    font_config_cat = ("", 9, "normal")
                    if income_by_cat:
                        display_name, truncated = self._get_truncated_text(max(income_by_cat, key=income_by_cat.get), font_config_cat, cell_width)
                        ttk.Label(category_frame, text=display_name, font=font_config_cat, foreground=INCOME_COLOR, anchor="center", background="white").pack(fill=tk.X)
                        if truncated: was_truncated = True
                    if expense_by_cat:
                        display_name, truncated = self._get_truncated_text(max(expense_by_cat, key=expense_by_cat.get), font_config_cat, cell_width)
                        ttk.Label(category_frame, text=display_name, font=font_config_cat, foreground=EXPENSE_COLOR, anchor="center", background="white").pack(fill=tk.X)
                        if truncated: was_truncated = True

                    font_config_amount = ("", 10, "normal")
                    income_total = sum(income_by_cat.values())
                    expense_total = sum(expense_by_cat.values())
                    
                    if income_total > 0:
                        text, truncated = self._get_truncated_text(f"+{income_total:,}", font_config_amount, cell_width)
                        ttk.Label(content_frame, text=text, foreground=INCOME_COLOR, font=font_config_amount, background="white", style="Indicator.TLabel").pack()
                        if truncated: was_truncated = True
                    if expense_total > 0:
                        text, truncated = self._get_truncated_text(f"-{expense_total:,}", font_config_amount, cell_width)
                        ttk.Label(content_frame, text=text, foreground=EXPENSE_COLOR, font=font_config_amount, background="white", style="Indicator.TLabel").pack()
                        if truncated: was_truncated = True

                    if was_truncated:
                        indicator_label = ttk.Label(day_cell, text="▼", foreground="grey", font=("", 8), style="Content.TLabel")
                        indicator_label.place(relx=1.0, rely=1.0, x=-2, y=-2, anchor="se")

                widgets_to_bind = [day_cell, header_frame, content_frame, date_canvas]
                if 'indicator_label' in locals() and indicator_label.winfo_exists(): widgets_to_bind.append(indicator_label)
                if 'category_frame' in locals() and category_frame.winfo_exists(): widgets_to_bind.extend([category_frame] + category_frame.winfo_children())
                
                if day_transactions:
                    tooltip = Tooltip(day_cell, self._format_tooltip_text(day_transactions))
                    for widget in widgets_to_bind: tooltip.bind_widget(widget); widget.bind("<Button-1>", lambda e, d=date_obj: self.on_date_click_callback(d))
                else:
                    for widget in widgets_to_bind: widget.bind("<Button-1>", lambda e, d=date_obj: self.on_date_click_callback(d))
    
    def _format_tooltip_text(self, transactions: List[Transaction]) -> str:
        text_parts = []; income_txs = sorted([tx for tx in transactions if tx.type == 'income'], key=lambda t: t.amount, reverse=True); expense_txs = sorted([tx for tx in transactions if tx.type == 'expense'], key=lambda t: t.amount, reverse=True)
        if income_txs: text_parts.append("収入:"); [text_parts.append(f"  + {tx.category}: ¥{tx.amount:,}") for tx in income_txs]
        if expense_txs:
            if text_parts: text_parts.append("")
            text_parts.append("支出:"); [text_parts.append(f"  - {tx.category}: ¥{tx.amount:,}") for tx in expense_txs]
        return "\n".join(text_parts)
    def go_to_prev_month(self): self.current_date = self.current_date.replace(day=1) - timedelta(days=1); self.render_calendar(); self.on_month_change_callback(self.current_date)
    def go_to_next_month(self): _, last_day = calendar.monthrange(self.current_date.year, self.current_date.month); self.current_date = self.current_date.replace(day=last_day) + timedelta(days=1); self.render_calendar(); self.on_month_change_callback(self.current_date)

class HouseholdAppGUI:
    def __init__(self, root: tk.Tk, ledger: Ledger):
        self.root = root; self.ledger = ledger
        self.todo_manager = TodoManager()
        self.add_window = None; self.settings_manager = SettingsManager()
        self.root.title("シンプル家計簿ダッシュボード"); self.root.geometry("1280x720"); self.root.resizable(True, True)
        self.default_font = font.nametofont("TkDefaultFont"); self.default_font.configure(family=plt.rcParams['font.family'], size=10)
        self.displayed_date_for_charts = date.today(); self._chart_data_cache = {}

        self.current_view = tk.StringVar(value="dashboard")
        self.current_view.trace_add("write", self._on_view_change)

        self.style = ttk.Style()
        self.style.configure("WhiteBG.TFrame", background="#ffffff")
        self.style.configure("WhiteBG.TLabel", background="#ffffff")
        self.style.configure("MonthHeader.TFrame", background="#808080")
        self.style.configure("MonthHeader.TLabel", background="#808080", foreground="#ffffff")
        
        self._create_widgets()
        initial_theme = self.settings_manager.get("app_theme")
        self._apply_theme(initial_theme)
        
        # 【修正】UIの初回更新を遅延させて呼び出す
        # これにより、ウィンドウのサイズが確定した後に描画が実行され、文字の省略を防ぐ
        self.root.after(50, self.initial_load)

    # 【修正】初回読み込み用のメソッドを新設
    def initial_load(self):
        """UIの初回更新処理。ウィンドウサイズ確定後に呼び出す。"""
        self.update_ui()
        self._on_view_change()

    def _create_widgets(self):
        nav_bar = ttk.Frame(self.root, style="Nav.TFrame")
        nav_bar.pack(fill=tk.X)
        
        btn_texts = {"dashboard": "📈 ダッシュボード", "todo": "✅ ToDoリスト", "settings": "⚙️ 設定"}
        for view_name, text in btn_texts.items():
            btn_frame = ttk.Frame(nav_bar, style="Nav.TFrame")
            btn_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            button = ttk.Radiobutton(btn_frame, text=text, variable=self.current_view, value=view_name, style="Nav.TRadiobutton")
            button.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self.content_header = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        summary_container = ttk.Frame(self.content_header)
        summary_container.pack(fill=tk.X, pady=5, padx=10)

        line1_frame = ttk.Frame(summary_container)
        line1_frame.pack(anchor="w")

        INCOME_COLOR = "#007aff"
        EXPENSE_COLOR = "#d62728"

        self.income_label = ttk.Label(line1_frame, text="今月の収入: ¥0", font=(self.default_font.cget("family"), 13), foreground=INCOME_COLOR)
        self.income_label.pack(side=tk.LEFT)
        self.expense_label = ttk.Label(line1_frame, text="今月の支出: ¥0", font=(self.default_font.cget("family"), 13), foreground=EXPENSE_COLOR)
        self.expense_label.pack(side=tk.LEFT, padx=(20, 0))
        
        self.balance_label = ttk.Label(summary_container, text="今月の収支: ¥0", font=(self.default_font.cget("family"), 18, "bold"))
        self.balance_label.pack(anchor="w", pady=(5,0))
        
        self.main_content_frame = ttk.Frame(self.root)
        self.main_content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.dashboard_frame = ttk.Frame(self.main_content_frame)
        self.dashboard_frame.columnconfigure(0, weight=1)
        self.dashboard_frame.columnconfigure(1, weight=4)
        self.dashboard_frame.rowconfigure(0, weight=1)

        left_pane = ttk.Frame(self.dashboard_frame)
        left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_pane.columnconfigure(0, weight=1)
        left_pane.rowconfigure(0, weight=1)
        left_pane.rowconfigure(1, weight=1)

        chart_container = ttk.Frame(left_pane, style="WhiteBG.TFrame")
        chart_container.grid(row=0, column=0, sticky="nsew", pady=(0, 5))

        analysis_title = ttk.Label(chart_container, text="月間レポート", font=(self.default_font.cget("family"), 14, "bold"), anchor="center", style="WhiteBG.TLabel")
        analysis_title.pack(pady=(5, 10), fill=tk.X)

        self.chart_nav_var = tk.StringVar(value="expense")
        chart_nav_frame = ttk.Frame(chart_container, style="WhiteBG.TFrame")
        chart_nav_frame.pack(pady=5, fill=tk.X)
        chart_nav_frame.columnconfigure((0,1,2), weight=1)

        chart_btn_texts = {"expense": "支出内訳", "income": "収入内訳", "balance": "収支バランス"}
        col = 0
        for value, text in chart_btn_texts.items():
            btn = ttk.Radiobutton(chart_nav_frame, text=text, variable=self.chart_nav_var, value=value, command=self._trigger_active_chart_update, style="ChartNav.TRadiobutton")
            btn.grid(row=0, column=col, sticky="ew", padx=2)
            col += 1

        charts_frame = ttk.Frame(chart_container, style="WhiteBG.TFrame")
        charts_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.chart_view_expense = ChartView(charts_frame, chart_type='expense', settings_manager=self.settings_manager, style="WhiteBG.TFrame")
        self.chart_view_income = ChartView(charts_frame, chart_type='income', settings_manager=self.settings_manager, style="WhiteBG.TFrame")
        self.chart_view_balance = ChartView(charts_frame, chart_type='balance', settings_manager=self.settings_manager, style="WhiteBG.TFrame")
        for cv in [self.chart_view_expense, self.chart_view_income, self.chart_view_balance]:
            cv.fig.patch.set_facecolor("#ffffff")
            cv.ax.set_facecolor("#ffffff")
        
        list_frame_container = ttk.Labelframe(left_pane, text="取引リスト")
        list_frame_container.grid(row=1, column=0, sticky="nsew", pady=(5, 0))
        self.list_canvas = tk.Canvas(list_frame_container, highlightthickness=0, background="#ffffff")
        scrollbar_tx = ttk.Scrollbar(list_frame_container, orient="vertical", command=self.list_canvas.yview)
        self.list_frame = ttk.Frame(self.list_canvas, style="WhiteBG.TFrame")
        self.list_frame.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_canvas.configure(yscrollcommand=scrollbar_tx.set)
        self.list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar_tx.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.list_canvas.bind_all("<MouseWheel>", self._on_tx_list_mousewheel, add="+")
        self.list_frame.bind_all("<MouseWheel>", self._on_tx_list_mousewheel, add="+")

        right_pane = ttk.Frame(self.dashboard_frame)
        right_pane.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.calendar_view = CalendarView(right_pane, style=self.style, ledger=self.ledger, todo_manager=self.todo_manager, on_date_click_callback=self._on_date_selected_from_calendar, on_month_change_callback=self._on_calendar_month_changed)
        self.calendar_view.pack(fill=tk.BOTH, expand=True)

        self.todo_frame = ttk.Frame(self.main_content_frame)
        todo_list_container = ttk.Frame(self.todo_frame)
        todo_list_container.pack(fill=tk.BOTH, expand=True)
        self.full_todo_view = TodoView(todo_list_container, self.todo_manager, self._on_todo_change)
        self.full_todo_view.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.settings_frame = SettingsView(self.main_content_frame, self.settings_manager, self._on_settings_changed)

    def _on_tx_list_mousewheel(self, event):
        if not (self.list_canvas.winfo_ismapped() and self.list_canvas.winfo_containing(event.x_root, event.y_root) == self.list_canvas):
            return

        if platform.system() == "Windows":
            scroll_units = -1 * (event.delta // 120)
        elif platform.system() == "Darwin":
             scroll_units = event.delta
        else:
            scroll_units = -1 if event.delta > 0 else 1
        self.list_canvas.yview_scroll(scroll_units, "units")

    def _bind_tx_list_mousewheel_recursive(self, widget):
        widget.bind("<MouseWheel>", self._on_tx_list_mousewheel)
        for child in widget.winfo_children():
            if isinstance(child, (ttk.Frame, ttk.Label)):
                 self._bind_tx_list_mousewheel_recursive(child)

    def _on_view_change(self, *args):
        view = self.current_view.get()
        self.content_header.pack_forget()
        self.dashboard_frame.pack_forget()
        self.todo_frame.pack_forget()
        self.settings_frame.pack_forget()
        
        if view == "dashboard":
            self.content_header.pack(fill=tk.X, before=self.main_content_frame)
            self.dashboard_frame.pack(fill=tk.BOTH, expand=True)
            self.root.after(100, self._trigger_active_chart_update)
        elif view == "todo":
            self.todo_frame.pack(fill=tk.BOTH, expand=True)
        elif view == "settings":
            self.settings_frame.pack(fill=tk.BOTH, expand=True)

    def _update_transaction_list(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        all_transactions = self.ledger.get_all_transactions()
        if not all_transactions: 
            ttk.Label(self.list_frame, text="取引履歴がありません", font=(self.default_font.cget("family"), 10, "italic"), style="WhiteBG.TLabel").pack(pady=20)
            return

        grouped_by_month = defaultdict(list)
        for tx in all_transactions: grouped_by_month[(tx.transaction_date.year, tx.transaction_date.month)].append(tx)
        
        latest_month_key = None
        if grouped_by_month:
            sorted_keys = sorted(grouped_by_month.keys(), reverse=True)
            if sorted_keys:
                latest_month_key = sorted_keys[0]

        default_family = self.default_font.cget("family")

        for month_key, transactions_in_month in sorted(grouped_by_month.items(), reverse=True):
            year, month = month_key
            month_header_frame = ttk.Frame(self.list_frame, style="MonthHeader.TFrame")
            month_header_frame.pack(fill=tk.X, pady=(10, 1), padx=5)
            month_header_frame.columnconfigure(0, weight=1)
            month_label = ttk.Label(month_header_frame, text=f"▶ {year}年 {month}月", font=(default_family, 12, "bold"), style="MonthHeader.TLabel")
            month_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
            days_container = ttk.Frame(self.list_frame, style="WhiteBG.TFrame")

            def create_toggler(container, header, label, y, m, txs):
                is_content_created = False
                def toggle(event=None):
                    nonlocal is_content_created
                    if container.winfo_viewable():
                        container.pack_forget(); label.config(text=f"▶ {y}年 {m}月")
                    else:
                        if not is_content_created:
                            self._create_month_content(container, txs)
                            self._bind_tx_list_mousewheel_recursive(container)
                            is_content_created = True
                        container.pack(fill=tk.X, padx=(15, 5), after=header); label.config(text=f"▼ {y}年 {m}月")
                return toggle

            toggler = create_toggler(days_container, month_header_frame, month_label, year, month, transactions_in_month)
            month_header_frame.bind("<Button-1>", toggler); month_label.bind("<Button-1>", toggler)

            if month_key == latest_month_key:
                self.root.after(10, toggler)

    def _create_month_content(self, parent_container, transactions_in_month):
        default_family = self.default_font.cget("family")
        days_in_month = defaultdict(list)
        for tx in transactions_in_month: days_in_month[tx.transaction_date].append(tx)

        for day, transactions_in_day in sorted(days_in_month.items(), reverse=True):
            day_header_frame = ttk.Frame(parent_container, padding=(0, 5), style="WhiteBG.TFrame")
            day_header_frame.pack(fill=tk.X, padx=5)
            day_header_frame.columnconfigure(0, weight=1)
            ttk.Label(day_header_frame, text=f"{day.day}日 ({'月火水木金土日'[day.weekday()]})", font=(default_family, 10, "bold"), style="WhiteBG.TLabel").grid(row=0, column=0, sticky="w")
            delete_button = ttk.Button(day_header_frame, text="🗑️", width=3, style="Toolbutton.TButton", command=lambda d=day: self._handle_delete_day(d))
            self.style.map("Toolbutton.TButton", background=[('active', '#e0e0e0'), ('!active', '#ffffff')])
            delete_button.grid(row=0, column=1, sticky="e")

            for tx in transactions_in_day: self._create_transaction_card(parent_container, tx.to_card_data())
    
    def _create_transaction_card(self, parent_frame: ttk.Frame, tx_data: dict):
        card_frame = ttk.Frame(parent_frame, padding=10, style="WhiteBG.TFrame")
        card_frame.pack(fill=tk.X, padx=5, pady=(0, 5))
        content_frame = ttk.Frame(card_frame, style="WhiteBG.TFrame"); content_frame.pack(fill=tk.X)
        default_family = self.default_font.cget("family")
        ttk.Label(content_frame, text=tx_data["category"], font=(default_family, 13, "bold"), style="WhiteBG.TLabel").pack(side=tk.LEFT)
        
        INCOME_COLOR = "#007aff"
        EXPENSE_COLOR = "#d62728"
        amount_color = INCOME_COLOR if tx_data["type"] == 'income' else EXPENSE_COLOR
        amount_label = ttk.Label(content_frame, text=tx_data["amount_str"], font=(default_family, 13, "bold"), foreground=amount_color, style="WhiteBG.TLabel")
        amount_label.pack(side=tk.RIGHT)
    
    def _update_summary(self):
        now = datetime.now(); income_total = self.ledger.get_income_summary_for_month(now.year, now.month); expense_total = self.ledger.get_expense_summary_for_month(now.year, now.month); balance = income_total - expense_total
        
        INCOME_COLOR = "#007aff"
        EXPENSE_COLOR = "#d62728"
        
        self.income_label.config(text=f"今月の収入: ¥{income_total:,}")
        self.expense_label.config(text=f"今月の支出: ¥{expense_total:,}")
        
        balance_color = INCOME_COLOR if balance >= 0 else EXPENSE_COLOR
        balance_sign = "+" if balance >= 0 else ""
        self.balance_label.config(text=f"今月の収支: {balance_sign}¥{balance:,}", foreground=balance_color)

    def update_ui(self): 
        self._update_summary(); self._trigger_active_chart_update(); self._update_transaction_list()
        self.full_todo_view.update_list()
        self.calendar_view.render_calendar()

    def _get_chart_data(self, year: int, month: int):
        cache_key = (year, month)
        if cache_key in self._chart_data_cache: return self._chart_data_cache[cache_key]
        expense_summary = self.ledger.get_category_summary_for_month(year, month); income_summary = self.ledger.get_income_category_summary_for_month(year, month); balance_summary = {'収入': self.ledger.get_income_summary_for_month(year, month), '支出': self.ledger.get_expense_summary_for_month(year, month)}
        data = {'expense': expense_summary, 'income': income_summary, 'balance': balance_summary}; self._chart_data_cache[cache_key] = data; return data

    def _invalidate_chart_cache_for_date(self, changed_date: date):
        cache_key = (changed_date.year, changed_date.month)
        if cache_key in self._chart_data_cache: del self._chart_data_cache[cache_key]

    def _trigger_active_chart_update(self, event=None):
        year, month = self.displayed_date_for_charts.year, self.displayed_date_for_charts.month
        chart_data = self._get_chart_data(year, month)
        
        selected_chart = self.chart_nav_var.get()
        
        self.chart_view_expense.pack_forget()
        self.chart_view_income.pack_forget()
        self.chart_view_balance.pack_forget()

        if selected_chart == "expense":
            self.chart_view_expense.pack(fill=tk.BOTH, expand=True)
            self.chart_view_expense.update_chart(year, month, chart_data['expense'], chart_data['balance'])
        elif selected_chart == "income":
            self.chart_view_income.pack(fill=tk.BOTH, expand=True)
            self.chart_view_income.update_chart(year, month, chart_data['income'], chart_data['balance'])
        elif selected_chart == "balance":
            self.chart_view_balance.pack(fill=tk.BOTH, expand=True)
            self.chart_view_balance.update_chart(year, month, {}, chart_data['balance'])

    def _on_todo_change(self): self.calendar_view.render_calendar()

    def _handle_delete_day(self, target_date: date):
        date_str = target_date.strftime('%Y年%m月%d日')
        if messagebox.askyesno("削除の確認", f"「{date_str}」の全ての取引を削除しますか？\nこの操作は元に戻せません。", parent=self.root):
            self._invalidate_chart_cache_for_date(target_date); deleted_count = self.ledger.delete_transactions_for_day(target_date)
            if deleted_count > 0: self.update_ui(); messagebox.showinfo("削除完了", f"{deleted_count}件の取引を削除しました。", parent=self.root)

    def _on_settings_changed(self):
        """ テーマや色設定の変更を適用し、UIを更新する """
        theme_key = self.settings_manager.get("app_theme")
        self._apply_theme(theme_key)
        self._trigger_active_chart_update()
        self.calendar_view.render_calendar()

    def _apply_theme(self, theme_key: str):
        themes_colors = {
            "default_light_gray": {"bg": "#f0f0f0", "comp_bg": "#ffffff", "accent": "#007aff", "header_bg": "#f8f9fa", "nav_bg": "#e8e8e8", "nav_selected_bg": "#ffffff", "nav_selected_fg": "#007aff"},
            "pastel_mint":        {"bg": "#f0f7f4", "comp_bg": "#ffffff", "accent": "#4db6ac", "header_bg": "#e6f0ed", "nav_bg": "#e0e8e6", "nav_selected_bg": "#ffffff", "nav_selected_fg": "#4db6ac"},
            "soft_lavender":      {"bg": "#f3f0f7", "comp_bg": "#ffffff", "accent": "#9575cd", "header_bg": "#ebe6f0", "nav_bg": "#e4e0e8", "nav_selected_bg": "#ffffff", "nav_selected_fg": "#9575cd"},
        }
        colors = themes_colors.get(theme_key, themes_colors["default_light_gray"])
        DEFAULT_TEXT_COLOR = "#000000"

        self.root.configure(bg=colors["bg"])
        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=DEFAULT_TEXT_COLOR)
        self.style.configure("TLabelframe", background=colors["bg"], foreground=DEFAULT_TEXT_COLOR)
        self.style.configure("TLabelframe.Label", background=colors["bg"], foreground=DEFAULT_TEXT_COLOR)
        
        self.style.configure("Content.TFrame", background=colors["comp_bg"])
        self.style.configure("Content.TLabel", background=colors["comp_bg"], foreground=DEFAULT_TEXT_COLOR)
        self.style.configure("CalendarDay.TFrame", background=colors["comp_bg"])

        self.style.configure("Content.TCheckbutton", background=colors["comp_bg"])
        self.style.map("Content.TCheckbutton",
            background=[('active', colors["comp_bg"])]
        )

        self.style.configure("Grid.TFrame", background=colors["bg"])
        self.style.configure("Toolbutton.TButton", padding=2, relief="flat", background=colors["comp_bg"])
        self.style.map("Toolbutton.TButton", background=[('active', '#d0d0d0')])
        
        self.style.configure("Nav.TFrame", background=colors["nav_bg"])
        self.style.map("Nav.TRadiobutton",
            background=[('!active', colors["nav_bg"]), ('selected', colors["nav_selected_bg"]), ('active', colors["comp_bg"])],
            foreground=[('!selected', 'gray'), ('selected', colors["nav_selected_fg"])]
        )
        
        self.style.configure("Theme.TRadiobutton",
            background=colors["bg"],
            foreground=DEFAULT_TEXT_COLOR
        )
        self.style.map("Theme.TRadiobutton",
            background=[('active', colors["bg"])]
        )

        self.style.map("ChartNav.TRadiobutton",
            background=[
                ('!selected', '#f0f0f0'),
                ('selected', colors["accent"]),
                ('active', '#e0e0e0')
            ],
            foreground=[
                ('!selected', DEFAULT_TEXT_COLOR),
                ('selected', 'white')
            ]
        )
        
        if hasattr(self, 'chart_view_expense'):
             for chart_view in [self.chart_view_expense, self.chart_view_income, self.chart_view_balance]:
                if hasattr(chart_view, 'fig'):
                    chart_view.fig.patch.set_facecolor(colors["comp_bg"])
                    chart_view.ax.set_facecolor(colors["comp_bg"])
                    chart_view.canvas.draw_idle()

        if hasattr(self, 'settings_frame'):
            self.settings_frame.canvas.configure(bg=colors["bg"])

        if hasattr(self, 'full_todo_view'):
            self.full_todo_view.canvas.configure(bg=colors["comp_bg"])
        
        if hasattr(self, 'calendar_view'):
            self.calendar_view.render_calendar()


    def _on_transaction_added(self, new_transaction: Transaction): self._invalidate_chart_cache_for_date(new_transaction.transaction_date); self.update_ui()
    
    def _on_date_selected_from_calendar(self, selected_date: date): 
        self._open_add_transaction_window(initial_date=selected_date)

    def _open_add_transaction_window(self, initial_date: date = None):
        if initial_date is None: initial_date = date.today()
        if self.add_window is None or not self.add_window.winfo_exists(): 
            self.add_window = AddTransactionWindow(self.root, self.ledger, self._on_transaction_added, initial_date=initial_date)
        else: 
            self.add_window.lift()

    def _on_calendar_month_changed(self, new_date: date):
        if self.displayed_date_for_charts.year != new_date.year or self.displayed_date_for_charts.month != new_date.month: self.displayed_date_for_charts = new_date; self._trigger_active_chart_update()

def main():
    my_ledger = Ledger()
    my_todo_manager = TodoManager()
    
    root = tk.Tk()
    
    style = ttk.Style(root)
    default_font_family = font.nametofont("TkDefaultFont").cget("family")
    
    style.configure("LargeAdd.TButton", font=(default_font_family, 12, "bold"), padding=(20, 8))

    style.layout("Nav.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})])
    style.configure("Nav.TRadiobutton", font=(default_font_family, 11, "bold"), padding=(10, 8), anchor="center", borderwidth=1, relief="solid")

    style.layout("ChartNav.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})])
    style.configure("ChartNav.TRadiobutton", font=(default_font_family, 9), padding=(5, 5), anchor="center", borderwidth=1, relief="solid")

    style.layout("Type.TRadiobutton", [("Radiobutton.padding", {"sticky": "nswe", "children": [("Radiobutton.label", {"sticky": "nswe"})]})])
    style.configure("Type.TRadiobutton", anchor="center", padding=(10, 5), borderwidth=1, relief="solid")
    style.map("Type.TRadiobutton",
        background=[('selected', '#007aff'), ('!selected', '#f0f0f0')],
        foreground=[('selected', 'white'), ('!selected', 'black')]
    )

    style.configure("WeekdayHeader.TFrame", background="#e8e8e8")

    app = HouseholdAppGUI(root, my_ledger)
    root.mainloop()

if __name__ == "__main__":
    main()
