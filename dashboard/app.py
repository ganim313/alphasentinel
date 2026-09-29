import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
"""
AlphaSentinel Streamlit Portfolio & Quant Dashboard.
Secured over Tailscale Private VPN ($0 Budget).
Enhanced with TradingView Interactive Charts and Multi-Agent Debate Inspector.
"""

import os
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import date
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

from src.db.session import get_read_connection
from src.notification.telegram_bot import is_system_halted, set_system_halt_state
from src.agents.manual_export import generate_web_ui_payload

load_dotenv()

# Configure Page
st.set_page_config(
    page_title="AlphaSentinel OS",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def check_password():
    """Returns `True` if the user had the correct password."""
    expected_password = os.getenv("DASHBOARD_PASSWORD")
    if not expected_password:
        st.error("⚠️ DASHBOARD_PASSWORD not set in .env file. Access Denied.")
        return False

    def password_entered():
        if st.session_state["password"] == expected_password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Dashboard Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

class SchedulerStatus(tuple):
    def __new__(cls, status_text: str, badge_type: str, pid: Optional[int] = None):
        return super().__new__(cls, (status_text, badge_type, pid))
    
    @property
    def status_text(self) -> str:
        return self[0]
        
    @property
    def badge_type(self) -> str:
        return self[1]
        
    @property
    def pid(self) -> Optional[int]:
        return self[2]
        
    @property
    def running(self) -> bool:
        return self[1] == "success"

    @property
    def detail(self) -> str:
        return self[0]

    def get(self, key, default=None):
        if key == "status_text": return self[0]
        if key == "badge_type": return self[1]
        if key == "pid": return self[2]
        if key == "running": return self.running
        if key == "detail": return self[0]
        return default

    def __getitem__(self, item):
        if isinstance(item, str):
            return self.get(item)
        return super().__getitem__(item)


def get_scheduler_status() -> SchedulerStatus:
    """
    Inspects process state and circuit breaker to determine live operating status.
    Returns: (status_text: str, badge_type: str, pid: Optional[int])
    badge_type: 'error', 'success', 'warning'
    """
    if is_system_halted():
        try:
            with get_read_connection() as conn:
                row = conn.execute("SELECT halt_reason FROM circuit_breaker_state WHERE id = 1;").fetchone()
                reason = row[0] if row and row[0] else "KILL_SWITCH_ACTIVE"
        except Exception:
            reason = "KILL_SWITCH_ACTIVE"
        return SchedulerStatus(f"🚨 SYSTEM STATUS: HALTED ({reason})", "error", None)

    # Check scheduler PID lock file
    lock_file = PROJECT_ROOT / "logs" / ".scheduler.lock"
    if lock_file.exists():
        try:
            with open(lock_file, "r") as f:
                content = f.read().strip()
                if content and content.isdigit():
                    pid = int(content)
                    import psutil
                    if psutil.pid_exists(pid):
                        proc = psutil.Process(pid)
                        # Check if process is running and not a zombie
                        if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                            return SchedulerStatus(f"🟢 SYSTEM STATUS: ACTIVE (SCHEDULER PID {pid})", "success", pid)
        except Exception as e:
            return SchedulerStatus(f"⚠️ SYSTEM STATUS: UNKNOWN (Lock check error: {e})", "warning", None)

    return SchedulerStatus("🟡 SYSTEM STATUS: IDLE (SCHEDULER STOPPED)", "warning", None)


if not check_password():
    st.stop()


# Helper: TradingView Interactive Candlestick Chart Widget
def render_tradingview_chart(symbol: str):
    """Embeds TradingView interactive widget into Streamlit for $0."""
    clean_sym = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    tv_widget_html = f"""
    <div class="tradingview-widget-container" style="height:480px;width:100%">
      <div id="tradingview_chart_{clean_sym}"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget({{
        "autosize": true,
        "symbol": "NSE:{clean_sym}",
        "interval": "D",
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#1E222D",
        "enable_publishing": false,
        "allow_symbol_change": true,
        "container_id": "tradingview_chart_{clean_sym}"
      }});
      </script>
    </div>
    """
    components.html(tv_widget_html, height=500)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222D;
        border-radius: 8px;
        padding: 15px;
        border-left: 4px solid #2962FF;
    }
    .stButton>button {
        width: 100%;
        border-radius: 6px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛡️ AlphaSentinel: Quant Trading OS")
st.caption("Autonomous 5-Tier Quant Architecture • Mode: 1-Month Paper Trading Validation Gate")

# -------------------------------------------------------------
# Top Status Bar & Emergency Kill Switch
# -------------------------------------------------------------
col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

status_text, badge_type, sched_pid = get_scheduler_status()
halted = is_system_halted()

with col1:
    if badge_type == "error":
        st.error(status_text)
    elif badge_type == "success":
        st.success(status_text)
    else:
        st.warning(status_text)

with col2:
    try:
        with get_read_connection() as conn:
            total_pos = conn.execute("SELECT COUNT(*) FROM positions WHERE status = 'OPEN';").fetchone()[0]
    except Exception:
        total_pos = 0
    st.metric(label="Active Open Positions", value=total_pos)

with col3:
    try:
        with get_read_connection() as conn:
            realized = conn.execute("SELECT COALESCE(SUM(realized_pnl), 0.0) FROM positions WHERE status != 'OPEN';").fetchone()[0]
    except Exception:
        realized = 0.0
    st.metric(label="Realized Paper P&L", value=f"₹{realized:,.2f}")

with col4:
    if halted:
        if st.button("▶️ RESUME SYSTEM"):
            set_system_halt_state(False, reason="WEB_DASHBOARD_RESUME")
            st.rerun()
    else:
        confirm_halt = st.checkbox("Confirm System Halt")
        if st.button("🛑 EMERGENCY HALT (/HALT_ALL)", type="primary", disabled=not confirm_halt):
            set_system_halt_state(True, reason="WEB_DASHBOARD_HALT")
            st.rerun()

st.divider()

# -------------------------------------------------------------
# Portfolio Evaluation Metrics (Phase 5)
# -------------------------------------------------------------
import json
metrics_path = PROJECT_ROOT / "dashboard" / "portfolio_metrics.json"

st.markdown("### 📈 Portfolio Evaluation Metrics")
met_col1, met_col2, met_col3 = st.columns(3)

if metrics_path.exists():
    try:
        with open(metrics_path, "r") as f:
            port_metrics = json.load(f)
        met_col1.metric("Win Rate", f"{port_metrics.get('win_rate', 0.0):.1f}%")
        met_col2.metric("Max Drawdown", f"₹{port_metrics.get('max_drawdown', 0.0):,.2f}")
        met_col3.metric("Sharpe Ratio", f"{port_metrics.get('sharpe_ratio', 0.0):.2f}")
    except Exception as e:
        met_col1.metric("Win Rate", "Error")
        met_col2.metric("Max Drawdown", "Error")
        met_col3.metric("Sharpe Ratio", "Error")
        st.warning(f"Failed to load metrics: {e}")
else:
    met_col1.metric("Win Rate", "Calculating...")
    met_col2.metric("Max Drawdown", "Calculating...")
    met_col3.metric("Sharpe Ratio", "Calculating...")

st.divider()


# -------------------------------------------------------------
# ML Model Metadata Display
# -------------------------------------------------------------
import json
meta_path = PROJECT_ROOT / "models" / "xgboost_global_meta.json"
if meta_path.exists():
    try:
        with open(meta_path, "r") as f:
            meta = json.load(f)
        
        st.markdown("### 🤖 Champion Model Info")
        mod_col1, mod_col2, mod_col3 = st.columns(3)
        mod_col1.metric("Last Training Date", meta.get("training_date", "N/A")[:10])
        mod_col2.metric("Validation AUC", f"{meta.get('validation_auc', 0.0):.4f}")
        mod_col3.metric("Training Rows", meta.get("row_count", "N/A"))
        st.divider()
    except Exception as e:
        st.warning(f"Failed to load model metadata: {e}")


# -------------------------------------------------------------
# Tabs: Positions, Morning Brief, Screener Candidates, Multi-Agent Debates, Export, Logs
# -------------------------------------------------------------
tab1, tab_mb, tab2, tab_debates, tab3, tab4 = st.tabs([
    "📊 Paper Portfolio", 
    "🌅 Morning Brief", 
    "🎯 Screener Candidates", 
    "🧠 Multi-Agent Debates", 
    "📤 Web UI Export", 
    "📝 System Logs"
])

with tab1:
    st.subheader("Active & Historical Positions")
    try:
        with get_read_connection() as conn:
            df_pos = conn.execute("""
                SELECT id, symbol, entry_date, entry_price, current_ltp, trailing_stop_loss, target_1, unrealized_pnl, status 
                FROM positions 
                ORDER BY created_at DESC;
            """).df()
    except Exception as e:
        df_pos = pd.DataFrame()
        st.error(f"Error loading positions: {e}")

    if not df_pos.empty:
        def color_pnl(val):
            if val is None: return ''
            try:
                val = float(val)
                if val > 0: return 'color: #00FF00'
                elif val < 0: return 'color: #FF0000'
            except (ValueError, TypeError):
                pass
            return ''
            
        styled_df = df_pos.style.map(color_pnl, subset=['unrealized_pnl'])
        
        st.dataframe(
            styled_df, 
            use_container_width=True,
            column_config={
                "entry_price": st.column_config.NumberColumn("Entry Price", format="₹%.2f"),
                "current_ltp": st.column_config.NumberColumn("Current LTP", format="₹%.2f"),
                "trailing_stop_loss": st.column_config.NumberColumn("Trailing SL", format="₹%.2f"),
                "target_1": st.column_config.NumberColumn("Target 1", format="₹%.2f"),
                "unrealized_pnl": st.column_config.NumberColumn("Unrealized P&L", format="₹%.2f"),
            }
        )
        
        open_positions = df_pos[df_pos['status'] == 'OPEN']
        if not open_positions.empty:
            st.divider()
            st.markdown("### ⚡ Quick Actions")
            col_a, col_b = st.columns([2, 2])
            with col_a:
                close_sym = st.selectbox("Select Open Position to Close", open_positions['symbol'].tolist())
            with col_b:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Close Position Now", type="primary"):
                    from src.db.queue_writer import db_write
                    from datetime import date
                    now_str = date.today().isoformat()
                    try:
                        db_write("""
                            UPDATE positions 
                            SET status='MANUALLY_CLOSED', realized_pnl = unrealized_pnl, unrealized_pnl=0.0, exit_date=?, exit_price=current_ltp
                            WHERE symbol=? AND status='OPEN'
                        """, (now_str, close_sym), sync=True)
                        st.success(f"Position for {close_sym} successfully closed!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Database error while closing position: {e}")
    else:
        st.info("No paper positions opened yet. The 03:15 PM screener will populate active setups.")

with tab_mb:
    st.subheader("🌅 Morning Pre-Market Macro Radar")
    try:
        from src.ingestion.macro_feeds import fetch_macro_weather_data
        macro_data = fetch_macro_weather_data()
        
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("US VIX Fear Gauge", f"{macro_data.get('us_vix', 0.0):.2f}")
        m_col2.metric("S&P 500 Overnight %", f"{macro_data.get('sp500_pct_change', 0.0):+.2f}%")
        m_col3.metric("Brent Crude Oil", f"${macro_data.get('crude_oil_price', 0.0):.2f}", f"{macro_data.get('crude_oil_pct_change', 0.0):+.2f}%")
        m_col4.metric("Market Regime", macro_data.get('market_regime', 'NEUTRAL'))
        
        st.divider()
        st.info(f"Target Cash Allocation: **{macro_data.get('target_cash_exposure_pct', 0.0)}%** (Macro Weather Score: {macro_data.get('macro_weather_score', 0.8):.2f}/1.0)")
    except Exception as e:
        st.error(f"Error loading Morning Brief: {e}")

with tab2:
    st.subheader("🎯 Screened Candidates & Interactive Charting")
    try:
        with get_read_connection() as conn:
            df_screen = conn.execute("""
                SELECT symbol, scan_date, trigger_price, 
                       ROUND(ml_probability * 100, 2) || '%' AS ml_probability, 
                       pattern_type AS vcp_pattern, 
                       mr_signal, 
                       pledge_trend_3m,
                       shield_passed, 
                       status 
                FROM screener_candidates 
                ORDER BY created_at DESC;
            """).df()
    except Exception as e:
        df_screen = pd.DataFrame()
        st.error(f"Error querying candidates: {e}")

    if not df_screen.empty:
        def color_status(val):
            if val == 'APPROVED': return 'color: #00FF00; font-weight: bold'
            if val == 'REJECTED': return 'color: #FF0000'
            return ''
        st.dataframe(df_screen.style.map(color_status, subset=['status']), use_container_width=True)
        
        st.divider()
        st.markdown("### 📈 Interactive TradingView Chart Viewer")
        candidate_symbols = df_screen['symbol'].unique().tolist()
        selected_tv_sym = st.selectbox("Select Candidate to Inspect Chart:", candidate_symbols)
        if selected_tv_sym:
            render_tradingview_chart(selected_tv_sym)
    else:
        st.info("No candidates scanned yet. Run `python scripts/run_live_preview.py` to trigger a scan.")

with tab_debates:
    st.subheader("🧠 Multi-Agent Adversarial Debate Transcripts")
    st.caption("LangGraph Deliberation Records (Bull Analyst vs Bear Trap Hunter vs Research Judge)")
    
    try:
        with get_read_connection() as conn:
            df_debates = conn.execute("""
                SELECT id, symbol, debate_date, conviction_score, tv_technical_rating, 
                       risk_manager_verdict, suggested_shares, stop_loss, target_1,
                       bull_thesis, bear_risks, judge_synthesis
                FROM debate_transcripts 
                ORDER BY created_at DESC;
            """).df()
    except Exception as e:
        df_debates = pd.DataFrame()
        st.error(f"Error querying debate transcripts: {e}")

    if not df_debates.empty:
        for idx, row in df_debates.iterrows():
            conviction = row.get("conviction_score") or 0.0
            verdict = row.get("risk_manager_verdict") or "PENDING"
            sym = row.get("symbol")
            
            with st.expander(f"🛡️ {sym} | Verdict: {verdict} | Conviction: ⭐️ {conviction:.1f}/10 | TV: {row.get('tv_technical_rating', 'N/A')}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Stop Loss", f"₹{row.get('stop_loss', 0.0):,.2f}")
                c2.metric("Target 1", f"₹{row.get('target_1', 0.0):,.2f}")
                c3.metric("Shares Sized", f"{row.get('suggested_shares', 0):,}")
                
                st.markdown("#### 🐂 Bull Analyst Thesis")
                st.info(row.get("bull_thesis") or "No thesis recorded.")
                
                st.markdown("#### 🐻 Bear Trap Hunter Critique")
                st.warning(row.get("bear_risks") or "No red flags recorded.")
                
                st.markdown("#### ⚖️ Chief Research Judge Synthesis")
                st.success(row.get("judge_synthesis") or "No synthesis recorded.")
    else:
        st.info("No debate transcripts recorded yet. Transcripts will automatically populate during the 03:15 PM screener runs.")

with tab3:
    st.subheader("Export Context for Web UI (Claude 3.5 Sonnet / ChatGPT-4o)")
    st.markdown("Use this to generate a dense JSON payload for free web-based LLM analysis.")

    try:
        with get_read_connection() as conn:
            candidates = conn.execute("SELECT symbol, trigger_price, adtv_20d, circuit_band FROM screener_candidates LIMIT 10;").fetchall()
    except Exception:
        candidates = []

    if candidates:
        cand_map = {c[0]: c for c in candidates}
        selected_sym = st.selectbox("Select Candidate Stock for Export:", list(cand_map.keys()))
        selected_cand = cand_map[selected_sym]
        
        sample_state = {
            "symbol": selected_sym,
            "trigger_price": selected_cand[1] or 150.0,
            "current_price": (selected_cand[1] or 150.0) * 0.99,
            "adtv_20d": selected_cand[2] or 8500000.0,
            "circuit_band": selected_cand[3] if selected_cand[3] is not None else 20.0,
            "fundamentals": {"pe_ratio": 21.0, "sector_pe": 30.0, "debt_to_equity": 0.15, "roce_pct": 18.0},
            "bull_thesis": "Minervini Stage 2 VCP setup with volume dry-up",
            "bear_risks": "General small-cap market volatility"
        }
        payload_text = generate_web_ui_payload(sample_state)

        st.code(payload_text, language="markdown")
        st.download_button(
            label="📥 Download Payload (.txt)",
            data=payload_text,
            file_name=f"alphasentinel_{selected_sym}_payload.txt",
            mime="text/plain"
        )
    else:
        st.info("No candidates available for export. Run screener first.")

with tab4:
    st.subheader("📝 Live System Logs")
    col_log1, col_log2 = st.columns([3, 1])
    
    log_files = {
        "03:15 PM Live Screener": "logs/live_preview.log",
        "06:00 PM EOD DB Reconciliation": "logs/eod.log",
        "Intraday Trailing Stop Loss Sentinel": "logs/sentinel.log",
        "09:09 AM Pre-Market Macro Radar": "logs/premarket.log"
    }
    
    with col_log1:
        selected_log_name = st.selectbox("Select Log Stream to View", list(log_files.keys()))
    with col_log2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Logs"):
            st.rerun()
            
    log_path = PROJECT_ROOT / log_files[selected_log_name]
    
    if log_path.exists():
        from collections import deque
        with open(log_path, "r", encoding="utf-8") as f:
            lines = deque(f, maxlen=100)
            log_content = "".join(lines)
        st.code(log_content, language="bash")
    else:
        st.info(f"Log file '{log_path}' not created yet. It will appear when the script runs.")
