import streamlit as st
import pandas as pd
from datetime import datetime, date
import db_manager as db

# Initialize DB
db.init_db()

st.set_page_config(page_title="Medication Tracker", page_icon="💊", layout="wide")

# Sidebar
st.sidebar.title("💊 Med Tracker")
page = st.sidebar.radio("Navigation", ["Dashboard", "Manage Medications", "History"])

if page == "Dashboard":
    st.title("📅 Daily Tracker")
    
    today = date.today().strftime("%Y-%m-%d")
    st.header(f"Schedule for {today}")
    
    schedule = db.get_medication_status(today)
    
    if not schedule:
        st.info("No medications scheduled for today.")
    else:
        # Calculate progress
        total_meds = len(schedule)
        taken_meds = sum(1 for item in schedule if item['taken'])
        progress = taken_meds / total_meds if total_meds > 0 else 0
        
        st.progress(progress)
        st.write(f"**Progress:** {int(progress * 100)}% completed")
        
        st.divider()
        
        for item in schedule:
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{item['name']}**")
                st.caption(f"Dosage: {item['dosage']}")
            
            with col2:
                st.write(f"🕒 {item['time']}")
                
            with col3:
                status_color = "green" if item['taken'] else "red"
                status_text = "Taken" if item['taken'] else "Pending"
                st.markdown(f":{status_color}[{status_text}]")
            
            with col4:
                # Unique key for each button using med_id and time
                key = f"{item['med_id']}_{item['time']}_{today}"
                if not item['taken']:
                    if st.button("Mark Taken", key=key):
                        db.log_medication(item['med_id'], today, item['time'], True)
                        st.rerun()
                else:
                    if st.button("Undo", key=key):
                        db.log_medication(item['med_id'], today, item['time'], False)
                        st.rerun()

elif page == "Manage Medications":
    st.title("💊 Manage Medications")
    
    with st.expander("➕ Add New Medication", expanded=True):
        with st.form("add_med_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Medication Name", placeholder="e.g. Ibuprofen")
                dosage = st.text_input("Dosage", placeholder="e.g. 200mg")
                
                st.subheader("Duration")
                start_date = st.date_input("Start Date", value=date.today())
                has_end_date = st.checkbox("Set End Date?")
                end_date = None
                if has_end_date:
                    end_date = st.date_input("End Date", value=date.today())
            
            with col2:
                frequency = st.selectbox("Frequency", ["Daily", "As Needed"])
                
                # Generate time options (every 30 mins)
                time_options = []
                for h in range(24):
                    for m in [0, 30]:
                        time_options.append(f"{h:02d}:{m:02d}")
                
                times = st.multiselect("Schedule Times", time_options, default=["09:00"])
            
            submitted = st.form_submit_button("Add Medication")
            
            if submitted:
                if name and times:
                    # Convert dates to string
                    start_str = start_date.strftime("%Y-%m-%d")
                    end_str = end_date.strftime("%Y-%m-%d") if end_date else None
                    
                    if end_date and start_date > end_date:
                         st.error("End date cannot be before start date.")
                    else:
                        db.add_medication(name, dosage, frequency, times, start_str, end_str)
                        st.success(f"Added {name} successfully!")
                        st.rerun()
                else:
                    st.error("Please provide at least a name and one scheduled time.")
    
    st.divider()
    st.subheader("Your Medications")
    
    meds = db.get_medications()
    if meds.empty:
        st.info("No medications added yet.")
    else:
        for _, med in meds.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4 = st.columns([2, 1, 2, 1])
                with c1:
                    st.subheader(med['name'])
                    st.caption(f"Dosage: {med['dosage']}")
                    
                    # Display Duration
                    duration_text = f"Start: {med['start_date']}"
                    if med['end_date']:
                        duration_text += f" | End: {med['end_date']}"
                    else:
                        duration_text += " | Ongoing"
                    st.caption(f"📅 {duration_text}")
                    
                with c2:
                    st.write(f"**Freq:** {med['frequency']}")
                with c3:
                    st.write(f"**Times:** {', '.join(med['times'])}")
                with c4:
                    if st.button("Delete", key=f"del_{med['id']}"):
                        db.delete_medication(med['id'])
                        st.rerun()

elif page == "History":
    st.title("📜 History")
    
    logs = db.get_logs()
    meds = db.get_medications()
    
    if logs.empty:
        st.info("No history available yet.")
    else:
        # Merge with med names
        if not meds.empty:
            history = pd.merge(logs, meds, left_on="medication_id", right_on="id", suffixes=('_log', '_med'))
            
            # Filter options
            selected_med = st.selectbox("Filter by Medication", ["All"] + list(meds['name'].unique()))
            
            if selected_med != "All":
                history = history[history['name'] == selected_med]
            
            # Show table
            st.dataframe(
                history[['date', 'time', 'name', 'dosage', 'taken', 'timestamp']].sort_values(by=['date', 'time'], ascending=False),
                use_container_width=True,
                hide_index=True
            )
            
            # Simple chart
            st.subheader("Adherence Overview")
            daily_stats = history.groupby('date')['taken'].mean().reset_index()
            daily_stats['taken'] = daily_stats['taken'] * 100
            st.bar_chart(daily_stats.set_index('date'))
        else:
            st.write(logs)
