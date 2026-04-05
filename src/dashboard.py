"""
Phase 13: Final Stability — Compatible Unified Dashboard
══════════════════════════════════════════════════════
Final high-performance dashboard with compatible Rich methods.
Uses unified Group for absolute rendering stability.
══════════════════════════════════════════════════════
"""
import time
import threading
from typing import Dict, List, Optional

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich.box import ROUNDED
from rich.console import Group

from strategy import BET_SEQUENCE

COINS = ["BTC", "ETH", "SOL", "XRP"]

class Dashboard:
    """Unified Renderable Dashboard for Maximum Stability."""

    def __init__(self, coins: list = None):
        self.start_time = time.time()
        self.coins = [c.upper() for c in (coins or COINS)]
        self._log_buffer: List[str] = [] 
        self._lock = threading.Lock()
        
        # ── FIXED: Auto-detect width and force terminal for SSH ──
        self.console = Console(force_terminal=True, color_system="auto")
        
        self._live: Optional[Live] = None
        self._last_render_ts = 0
        self._current_renderable = Panel("Initializing Dashboard...", border_style="yellow")

    def log(self, msg: str):
        """Thread-safe logging."""
        ts = time.strftime("%H:%M:%S")
        with self._lock:
            # Defensive cleaning for rich markup injection
            clean = str(msg).replace("[", "［").replace("]", "］")
            self._log_buffer.append(f"[grey50]{ts}[/] {clean}")
            self._log_buffer = self._log_buffer[-10:]

    def log_error(self, msg: str):
        self.log(f"[bold red]✗ {msg}[/]")

    def live_context(self):
        """Live context (4Hz for maximum stability and low CPU)."""
        self._live = Live(self._current_renderable, console=self.console, 
                          refresh_per_second=4, screen=True, auto_refresh=True)
        return self._live

    def render(self, market_states: Dict, mg_steps: Dict,
               pending: Dict, trade_log: List, wallet_bal: float,
               dry_run: bool = True, candle_history: Dict = None,
               last_bal_ts: int = 0):
        """Builds one unified renderable to ensure perfectly synced levels."""
        now = time.time()
        if now - self._last_render_ts < 0.15:
            return
        self._last_render_ts = now

        # 1. HEADER
        runtime = self._fmt_time(now - self.start_time)
        mode = "[bold yellow]DRY[/]" if dry_run else "[bold red]LIVE[/]"
        in_bets = sum(p.get("amount", 0) for p in (pending or {}).values() if p)
        age = int(now - last_bal_ts) if last_bal_ts > 0 else 0
        age_str = f" [dim]({age}s)[/]" if age > 10 else ""

        h_msg = f" ◆ [bold white]FASTBOT[/] │ ⏱ [green]{runtime}[/] │ {mode} │ 💰 [bold green]${wallet_bal:,.2f}[/]{age_str} │ 🔒 [yellow]${in_bets:,.2f}[/]"
        header = Panel(Align.center(Text.from_markup(h_msg)), border_style="cyan", box=ROUNDED)

        # 2. MARKETS
        m_table = Table(box=None, expand=True, header_style="bold cyan")
        m_table.add_column("COIN")
        m_table.add_column("TIME", justify="center")
        m_table.add_column("UP ASK", justify="right", style="green")
        m_table.add_column("DN ASK", justify="right", style="red")
        m_table.add_column("BIAS", justify="center")
        m_table.add_column("MARTINGALE", justify="left")
        m_table.add_column("POSITION", justify="left")

        for c in self.coins:
            ms = (market_states or {}).get(c, {})
            st = (mg_steps or {}).get(c, 0)
            pen = (pending or {}).get(c)

            t_val = self._fmt_timer(ms.get("seconds_till_end", 300))
            up, dn = ms.get("up_ask", 0), ms.get("down_ask", 0)
            bias = f"[green]▲[/]" if up > dn else f"[red]▼[/]" if up < dn else "·"
            blocks = "".join(["[red]●[/]" if i < st else "[bold yellow]◉[/]" if i == st else "[dim]○[/]" for i in range(len(BET_SEQUENCE))])
            
            if pen:
                p_c = "green" if pen["direction"]=="YES" else "red"
                pos = f"[bold {p_c}]{'UP' if pen['direction']=='YES' else 'DN'} ${pen['amount']:.0f}[/] @{pen['price']:.3f}"
            else:
                pos = "[dim]· idle[/]"

            m_table.add_row(c, t_val, f"{up:.3f}", f"{dn:.3f}", bias, blocks, pos)
        
        # 2.1 Use narrow layout if terminal width < 90
        is_narrow = self.console.width < 90
        markets = Panel(
            m_table, 
            title="[bold white]MARKETS[/]", 
            border_style="grey37",
            padding=(0, 1) if is_narrow else (1, 1)
        )

        # 3. FOOTER
        f_grid = Table.grid(expand=True)
        f_grid.add_column(ratio=3)
        f_grid.add_column(ratio=2)

        tr_text = Text()
        if not trade_log:
            tr_text.append(" Waiting for trades...", style="dim")
        else:
            for t in list(reversed(trade_log))[:6]:
                won = t.get("won", False)
                clr = "green" if won else "red"
                sign = "+" if t.get("pnl", 0) >= 0 else ""
                tr_text.append(Text.from_markup(f" {'✓' if won else '✗'} [bold]{t['coin']}[/] {'UP' if t['direction']=='YES' else 'DN'} ${t['amount']:.0f} [bold {clr}]{sign}${t['pnl']:.2f}[/]\n"))
        
        lg_text = Text()
        with self._lock:
            for line in self._log_buffer:
                lg_text.append(Text.from_markup(f" {line}\n"))
        
        f_grid.add_row(
            Panel(tr_text, title="[bold]TRADES[/]", border_style="grey37", expand=True, height=8 if is_narrow else 10),
            Panel(lg_text, title="[bold]LOGS[/]", border_style="grey37", expand=True, height=8 if is_narrow else 10)
        )

        # 4. Final Assemblage & Push to Live update
        self._current_renderable = Group(header, markets, f_grid)
        if self._live:
            self._live.update(self._current_renderable)

    @staticmethod
    def _fmt_time(secs: float) -> str:
        s = int(secs)
        return f"{s // 60}m{s % 60:02d}s"

    @staticmethod
    def _fmt_timer(secs: int) -> str:
        m, s = divmod(max(0, secs), 60)
        return f"{m:02d}:{s:02d}"
