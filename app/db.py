import sqlite3
import json
from datetime import datetime, timedelta
import pathlib

DB_PATH = pathlib.Path("data/analytics.db")

def init_db():
    """Initialize the SQLite database."""
    # Ensure data directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create query_logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS query_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_id TEXT,
            query_text TEXT,
            answer_text TEXT,
            sources_json TEXT,
            confidence_score REAL,
            latency_ms REAL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            token_count INTEGER DEFAULT 0
        )
    ''')
    
    # Migration: Add columns if they don't exist
    try:
        c.execute("ALTER TABLE query_logs ADD COLUMN input_tokens INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    try:
        c.execute("ALTER TABLE query_logs ADD COLUMN output_tokens INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    
    # Session Migrations
    try:
        c.execute("ALTER TABLE chat_sessions ADD COLUMN summary TEXT")
    except sqlite3.OperationalError: pass

    # Create chat_sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            summary TEXT,
            created_at TEXT
        )
    ''')
    
    # Create chat_messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            sources_json TEXT,
            timestamp TEXT,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(session_id)
        )
    ''')
    conn.commit()
    conn.close()

def log_query(session_id, query_text, answer_text, sources, confidence_score, latency_ms, input_tokens=0, output_tokens=0):
    """Log a query event to the database (Analytics)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        timestamp = datetime.utcnow().isoformat()
        sources_json = json.dumps(sources)
        
        # Calculate total for backward compatibility if needed, though we use split
        total_tokens = input_tokens + output_tokens
        
        c.execute('''
            INSERT INTO query_logs (timestamp, session_id, query_text, answer_text, sources_json, confidence_score, latency_ms, input_tokens, output_tokens, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, session_id, query_text, answer_text, sources_json, confidence_score, latency_ms, input_tokens, output_tokens, total_tokens))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging query: {e}")

# --- Chat History Helpers ---

def create_session(session_id, title="New Chat"):
    """Create a new chat session."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        c.execute('INSERT OR IGNORE INTO chat_sessions (session_id, title, created_at) VALUES (?, ?, ?)', 
                  (session_id, title, created_at))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error creating session: {e}")

def get_recent_sessions(limit=10):
    """Get recent chat sessions ordered by last message time."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Order by last message timestamp, fallback to created_at
        c.execute('''
            SELECT s.session_id, s.title, s.summary, s.created_at, MAX(m.timestamp) as last_active
            FROM chat_sessions s
            LEFT JOIN chat_messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY COALESCE(MAX(m.timestamp), s.created_at) DESC
            LIMIT ?
        ''', (limit,))
        
        sessions = [dict(row) for row in c.fetchall()]
        conn.close()
        return sessions
    except Exception as e:
        print(f"Error getting sessions: {e}")
        return []

def update_session_title(session_id, title):
    """Update session title."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE chat_sessions SET title = ? WHERE session_id = ?', (title, session_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating title: {e}")

def update_session_summary(session_id, summary):
    """Update session executive summary."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE chat_sessions SET summary = ? WHERE session_id = ?', (summary, session_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating summary: {e}")

def add_message(session_id, role, content, sources=None):
    """Add a message to a session."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        timestamp = datetime.utcnow().isoformat()
        sources_json = json.dumps(sources) if sources else None
        
        c.execute('''
            INSERT INTO chat_messages (session_id, role, content, sources_json, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, role, content, sources_json, timestamp))
        
        # Naive titling removed. Handled by LLM via background task now.
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error adding message: {e}")

def get_session_messages(session_id):
    """Get all messages for a session."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM chat_messages WHERE session_id = ? ORDER BY id ASC', (session_id,))
        rows = []
        for r in c.fetchall():
            d = dict(r)
            if d['sources_json']:
                try:
                    d['sources'] = json.loads(d['sources_json'])
                except:
                    d['sources'] = []
            else:
                d['sources'] = []
            rows.append(d)
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return []

def get_session_last_active(session_id):
    """Get timestamp of the last message in a session (or creation time). Returns unix epoch."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 1. Check last message
        c.execute('SELECT timestamp FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 1', (session_id,))
        row = c.fetchone()
        
        ts_str = None
        if row:
            ts_str = row[0]
        else:
            # 2. Fallback to session creation
            c.execute('SELECT created_at FROM chat_sessions WHERE session_id = ?', (session_id,))
            row = c.fetchone()
            if row:
                ts_str = row[0]
                
        conn.close()
        
        if ts_str:
            # Parse ISO string to unix timestamp
            # Handle potential Z or no Z
            dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            return dt.timestamp()
            
        return None
    except Exception as e:
        # print(f"Error checking activity for {session_id}: {e}")
        return None

def clear_all_history():
    """Clear all chat history and sessions."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM chat_messages")
        c.execute("DELETE FROM chat_sessions")
        # Optional: Keep query_logs for analytics or delete them too?
        # User said "recent sessions", implying chat UI. Let's keep logs for now unless asked.
        conn.commit()
        conn.close()
        print("Chat history cleared from DB.")
    except Exception as e:
        print(f"Error clearing history: {e}")

def delete_session(session_id):
    """Delete a specific session and its messages."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        # Keeping query_logs for overall analytics history
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error deleting session {session_id}: {e}")

def get_stats():
    """Retrieve partial analytics stats."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # 1. Total Queries
        c.execute("SELECT COUNT(*) as count FROM query_logs")
        total_queries = c.fetchone()['count']
        
        # 2. Active Sessions (Last 24h approximation: Unique Sessions in logs)
        # Using chat_sessions table for more accurate count of "Active" users if we logged login, but here use logs
        c.execute("SELECT COUNT(DISTINCT session_id) as count FROM query_logs")
        unique_sessions = c.fetchone()['count']
        
        # 3. Avg Latency
        c.execute("SELECT AVG(latency_ms) as avg_lat FROM query_logs")
        avg_latency = c.fetchone()['avg_lat'] or 0.0
        
        # 4. Avg Confidence
        c.execute("SELECT AVG(confidence_score) as avg_conf FROM query_logs")
        avg_score = c.fetchone()['avg_conf'] or 0.0
        
        # 5. Token Usage
        c.execute("SELECT SUM(input_tokens) as input, SUM(output_tokens) as output FROM query_logs")
        tokens = c.fetchone()
        input_tokens = tokens['input'] or 0
        output_tokens = tokens['output'] or 0
        
        # 6. Recent Logs
        c.execute("SELECT timestamp, query_text, confidence_score, latency_ms FROM query_logs ORDER BY id DESC LIMIT 50")
        recent_logs = [dict(row) for row in c.fetchall()]
        
        # 7. Storage Volume
        total_size = 0
        try:
            root_dir = DB_PATH.parent
            for entry in root_dir.rglob('*'):
                if entry.is_file():
                    total_size += entry.stat().st_size
        except:
            pass
        
        conn.close()
        
        return {
            "total_queries": total_queries,
            "unique_sessions": unique_sessions,
            "avg_latency": round(avg_latency, 2),
            "avg_score": round(avg_score, 2),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "storage_bytes": total_size,
            "recent_logs": recent_logs
        }
    except Exception as e:
        print(f"Error fetching stats: {e}")
        return {}

def get_timeseries_stats(range_type='7d', custom_start=None, custom_end=None):
    """
    Retrieve timeseries data for charts with dynamic range.
    range_type: 'today', '7d', '30d', 'custom'
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        now = datetime.utcnow()
        start_dt = now
        end_dt = now
        
        # 1. Determine Time Window
        if range_type == 'today':
            start_dt = now - timedelta(hours=24) # actually "Past 24h" logic for 'today' view or specific day? 
            # User wants "Today" which usually implies 00:00 to Now, but "Last 24h" is smoother. 
            # Let's stick to "Last 24h" for specific 'today' toggle as implied by previous code, 
            # OR we can do actual calendar day. The image showed "Today", "Last 7 Days". 
            # "Today" usually means since midnight. "Last 7 Days" means rolling.
            # Let's stick to Rolling windows for smoother charts? 
            # Actually image says "Today", "Last 7 Days".
            # Let's interpret "Today" as 00:00 today to now.
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range_type == '7d':
            start_dt = now - timedelta(days=7)
        elif range_type == '30d':
            start_dt = now - timedelta(days=30)
        elif range_type == 'custom' and custom_start:
            try:
                start_dt = datetime.fromisoformat(custom_start.replace('Z', ''))
                if custom_end:
                    end_dt = datetime.fromisoformat(custom_end.replace('Z', ''))
            except:
                start_dt = now - timedelta(days=7) # Fallback

        # 2. Determine Grouping (Hour vs Day)
        # If window <= 24h -> Hourly
        # If window > 24h -> Daily
        duration_hours = (end_dt - start_dt).total_seconds() / 3600
        group_by = 'hour' if duration_hours <= 25 else 'day'
        
        # Generate buckets
        buckets = []
        if group_by == 'hour':
            # Hourly buckets from start to end
            current = start_dt
            while current <= end_dt:
                buckets.append(current)
                current += timedelta(hours=1)
        else:
            # Daily buckets
            current = start_dt
            while current <= end_dt:
                buckets.append(current)
                current += timedelta(days=1)
                
        num_buckets = len(buckets)
        
        stats = {
            "queries": [0] * num_buckets,
            "sessions": [0] * num_buckets,
            "latency": [0.0] * num_buckets,
            "ingestion": [0] * num_buckets,
            "queries_total": 0,
            "sessions_total": 0,
            "volume_total": 0,
            "latency_avg": 0.0,
            "confidence_avg": 0.0,
            "p50_score": 0.0,
            "p90_score": 0.0,
            "trend_queries": 0.0,
            "trend_volume": 0.0,
            "labels": [] # For X-axis
        }
        
        # Populate Labels
        for dt in buckets:
            if group_by == 'hour':
                stats["labels"].append(dt.strftime('%H:%M'))
            else:
                stats["labels"].append(dt.strftime('%d %b'))

        # 3. Query Data
        c.execute('''
            SELECT timestamp, session_id, latency_ms, confidence_score, input_tokens, output_tokens
            FROM query_logs 
            WHERE timestamp >= ? AND timestamp <= ?
        ''', (start_dt.isoformat(), end_dt.isoformat()))
        rows = [dict(row) for row in c.fetchall()]
        
        bucket_data = {i: {"q": 0, "s": set(), "l_sum": 0, "l_cnt": 0} for i in range(num_buckets)}
        
        all_scores = []
        total_lat = 0
        total_conf = 0
        
        for r in rows:
            try:
                ts = datetime.fromisoformat(r['timestamp'])
                # Find bucket index
                # Simple approximation: index = (ts - start) / step
                if group_by == 'hour':
                    idx = int((ts - start_dt).total_seconds() / 3600)
                else:
                    idx = int((ts - start_dt).total_seconds() / 86400)
                
                if 0 <= idx < num_buckets:
                    bucket_data[idx]["q"] += 1
                    bucket_data[idx]["s"].add(r['session_id'])
                    lat = r['latency_ms'] or 0
                    bucket_data[idx]["l_sum"] += lat
                    bucket_data[idx]["l_cnt"] += 1
                
                total_lat += (r['latency_ms'] or 0)
                conf = r['confidence_score'] or 0
                total_conf += conf
                all_scores.append(conf)
            except:
                continue

        # Fill Series
        for i in range(num_buckets):
            stats["queries"][i] = bucket_data[i]["q"]
            stats["sessions"][i] = len(bucket_data[i]["s"])
            if bucket_data[i]["l_cnt"] > 0:
                stats["latency"][i] = round(bucket_data[i]["l_sum"] / bucket_data[i]["l_cnt"], 1)
        
        stats["queries_total"] = len(rows)
        stats["sessions_total"] = len(set(r['session_id'] for r in rows))
        stats["latency_avg"] = round(total_lat / len(rows), 2) if rows else 0.0
        stats["confidence_avg"] = round(total_conf / len(rows), 2) if rows else 0.0
        
        # 4. P50 / P90
        if all_scores:
            all_scores.sort()
            n = len(all_scores)
            stats["p50_score"] = round(all_scores[int(n * 0.50)], 2)
            stats["p90_score"] = round(all_scores[int(n * 0.90)], 2) if int(n * 0.90) < n else all_scores[-1]

        # 5. Ingestion (File System) & Trends
        # Window duration
        delta = end_dt - start_dt
        days_duration = max(delta.days, 1)
        
        trend_label_q = ""
        trend_label_v = ""
        
        # Trend Logic
        # A) Short Duration (< 7 days) -> Compare vs Previous same duration
        # B) Long Duration (>= 7 days) -> Compare Rate vs Previous 7 days (Last Week)
        
        if days_duration < 7:
            # Prev Window = [start - duration, start]
            prev_start = start_dt - delta
            prev_end = start_dt
            
            # Label
            if range_type == 'today':
                trend_label_q = "vs yesterday"
            elif range_type == 'custom':
                 trend_label_q = f"vs prev {int(delta.total_seconds()/86400) or 1}d"
            else:
                 trend_label_q = "vs prev period" # Generic fallback
                 
            # Queries Trend
            c.execute('''SELECT COUNT(*) FROM query_logs WHERE timestamp >= ? AND timestamp < ?''', (prev_start.isoformat(), prev_end.isoformat()))
            prev_q = c.fetchone()[0] or 0
            
            if prev_q > 0:
                stats["trend_queries"] = round(((stats["queries_total"] - prev_q) / prev_q) * 100, 1)
            else:
                stats["trend_queries"] = 100.0 if stats["queries_total"] > 0 else 0.0
                
            # Volume Trend Logic (later) - uses same window
            pass 

        else:
            # Long Duration -> Compare Daily Rate vs Prev 7 Days
            # Prev 7 Days Window = [start - 7d, start]
            prev_start = start_dt - timedelta(days=7)
            prev_end = start_dt
            trend_label_q = "vs last week"
            
            # Queries Rate
            c.execute('''SELECT COUNT(*) FROM query_logs WHERE timestamp >= ? AND timestamp < ?''', (prev_start.isoformat(), prev_end.isoformat()))
            prev_week_total = c.fetchone()[0] or 0
            prev_daily_rate = prev_week_total / 7
            
            curr_daily_rate = stats["queries_total"] / days_duration
            
            if prev_daily_rate > 0:
                stats["trend_queries"] = round(((curr_daily_rate - prev_daily_rate) / prev_daily_rate) * 100, 1)
            else:
                stats["trend_queries"] = 100.0 if curr_daily_rate > 0 else 0.0

        stats["trend_label_queries"] = trend_label_q
        stats["trend_label_volume"] = trend_label_q # Same logic for volume

        # Token Sums
        c.execute('''SELECT SUM(input_tokens), SUM(output_tokens) FROM query_logs WHERE timestamp >= ? AND timestamp <= ?''', (start_dt.isoformat(), end_dt.isoformat()))
        toks = c.fetchone()
        stats["input_tokens"] = toks[0] or 0
        stats["output_tokens"] = toks[1] or 0

        # Ingestion Volume (Approximation)
        try:
            root_dir = DB_PATH.parent
            vol_buckets = {i: 0 for i in range(num_buckets)}
            total_vol = 0
            
            # For trends
            vol_prev_period = 0 # For short duration
            vol_prev_week = 0   # For long duration
            
            for entry in root_dir.rglob('*'):
                if entry.is_file():
                    try:
                        mtime = datetime.utcfromtimestamp(entry.stat().st_mtime)
                        size = entry.stat().st_size
                        
                        # Main Window
                        if start_dt <= mtime <= end_dt:
                            total_vol += size
                            if group_by == 'hour':
                                idx = int((mtime - start_dt).total_seconds() / 3600)
                            else:
                                idx = int((mtime - start_dt).total_seconds() / 86400)
                            if 0 <= idx < num_buckets:
                                vol_buckets[idx] += size
                        
                        # Trend Window
                        if days_duration < 7:
                            if prev_start <= mtime < prev_end:
                                vol_prev_period += size
                        else:
                            if prev_start <= mtime < prev_end:
                                vol_prev_week += size
                                
                    except:
                        pass
            
            for i in range(num_buckets):
                stats["ingestion"][i] = vol_buckets[i]
            
            stats["volume_total"] = total_vol
            
            # Calculate Volume Trend
            if days_duration < 7:
                if vol_prev_period > 0:
                    stats["trend_volume"] = round(((total_vol - vol_prev_period) / vol_prev_period) * 100, 1)
                else:
                    stats["trend_volume"] = 100.0 if total_vol > 0 else 0.0
            else:
                # Rate comparison
                vol_rate_prev = vol_prev_week / 7
                vol_rate_curr = total_vol / days_duration
                if vol_rate_prev > 0:
                    stats["trend_volume"] = round(((vol_rate_curr - vol_rate_prev) / vol_rate_prev) * 100, 1)
                else:
                    stats["trend_volume"] = 100.0 if vol_rate_curr > 0 else 0.0
                 
        except Exception as e:
            print(f"Error scanning ingestion: {e}")

        conn.close()
        return stats

    except Exception as e:
        print(f"Error fetching timeseries stats: {e}")
        return {}
