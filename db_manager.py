import sqlite3
import json
from datetime import datetime
import pandas as pd

DB_FILE = "medication_tracker.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create medications table
    c.execute('''
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            times TEXT,
            start_date TEXT,
            end_date TEXT
        )
    ''')
    
    # Check for new columns in existing table (migration)
    c.execute("PRAGMA table_info(medications)")
    columns = [info[1] for info in c.fetchall()]
    
    if 'start_date' not in columns:
        c.execute("ALTER TABLE medications ADD COLUMN start_date TEXT")
    
    if 'end_date' not in columns:
        c.execute("ALTER TABLE medications ADD COLUMN end_date TEXT")
    
    # Create logs table
    c.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER,
            date TEXT,
            time TEXT,
            taken INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (medication_id) REFERENCES medications (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_medication(name, dosage, frequency, times, start_date=None, end_date=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # times should be a list, convert to json string for storage
    times_json = json.dumps(times)
    c.execute('''
        INSERT INTO medications (name, dosage, frequency, times, start_date, end_date) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, dosage, frequency, times_json, start_date, end_date))
    conn.commit()
    conn.close()

def delete_medication(med_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM medications WHERE id = ?', (med_id,))
    c.execute('DELETE FROM logs WHERE medication_id = ?', (med_id,))
    conn.commit()
    conn.close()

def get_medications():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM medications", conn)
    conn.close()
    # Convert times from json string back to list
    if not df.empty:
        df['times'] = df['times'].apply(lambda x: json.loads(x) if x else [])
    return df

def log_medication(med_id, date, time, taken):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check if already logged for this slot
    c.execute('SELECT id FROM logs WHERE medication_id = ? AND date = ? AND time = ?', (med_id, date, time))
    existing = c.fetchone()
    
    if existing:
        c.execute('UPDATE logs SET taken = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?', (1 if taken else 0, existing[0]))
    else:
        c.execute('INSERT INTO logs (medication_id, date, time, taken) VALUES (?, ?, ?, ?)',
                  (med_id, date, time, 1 if taken else 0))
    
    conn.commit()
    conn.close()

def get_logs(date=None):
    conn = sqlite3.connect(DB_FILE)
    query = "SELECT * FROM logs"
    params = ()
    if date:
        query += " WHERE date = ?"
        params = (date,)
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_medication_status(date_str):
    """
    Returns a merged view of medications and their status for a specific date.
    """
    meds = get_medications()
    logs = get_logs(date_str)
    
    if meds.empty:
        return []

    daily_schedule = []
    
    for _, med in meds.iterrows():
        # Check if medication is active for this date
        # If start_date exists, date_str must be >= start_date
        # If end_date exists, date_str must be <= end_date
        
        is_active = True
        
        if med['start_date']:
            if date_str < med['start_date']:
                is_active = False
        
        if med['end_date']:
            if date_str > med['end_date']:
                is_active = False
        
        if not is_active:
            continue

        for time in med['times']:
            # Find log for this specific med, date, and time
            log_entry = logs[(logs['medication_id'] == med['id']) & (logs['time'] == time)]
            is_taken = False
            if not log_entry.empty:
                is_taken = bool(log_entry.iloc[0]['taken'])
            
            daily_schedule.append({
                'med_id': med['id'],
                'name': med['name'],
                'dosage': med['dosage'],
                'time': time,
                'taken': is_taken
            })
            
    # Sort by time
    daily_schedule.sort(key=lambda x: x['time'])
    return daily_schedule
