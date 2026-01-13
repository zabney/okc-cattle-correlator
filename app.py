import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

# --- INITIAL APP SETUP ---
st.set_page_config(page_title="OKC Cattle Correlator", layout="wide")

# --- DATA FETCHING (HOLISTIC & DEFENSIVE) ---
@st.cache_data(ttl=3600)
def fetch_verified_data():
    api_url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        response = requests.get(api_url, auth=HTTPBasicAuth('pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y', ''), timeout=15)
        raw_json = response.json().get('results', [])
        
        if not raw_json:
            return None, "USDA report is currently empty or unavailable."
        
        df = pd.DataFrame(raw_json)
        
        # HOLISTIC FIX: Force all text to uppercase to avoid 'Steer' vs 'STEER' errors
        df['class'] = df['class'].astype(str).str.upper()
        df['frame_muscle'] = df['frame_muscle'].astype(str).str.upper()
        
        # Filter for only Steers and Heifers using fuzzy matching
        feeder_df = df[df['class'].str.contains("STEER|HEIFER", na=False)].copy()
        
        if feeder_df.empty:
            return None, "Found data, but no Steers or Heifers detected."
            
        return feeder_df, "Success"
    except Exception as e:
        return None, f"Connection Error: {str(e)}"

# --- APP EXECUTION ---
data, status = fetch_verified_data()

if data is not None:
    # Use standard labels for the UI
    data['DisplayClass'] = data['class'].apply(lambda x: "Steers" if "STEER" in x else "Heifers")
    
    with st.sidebar:
        st.header("1. Selection")
        selected_sex = st.radio("Type", ["Steers", "Heifers"])
        sex_df = data[data['DisplayClass'] == selected_sex]
        
        selected_grade = st.selectbox("Grade", sorted(sex_df['frame_muscle'].unique()))
        
        st.divider()
        st.header("2. Economics")
        adg = st.slider("ADG", 0.5, 4.0, 2.2)
        cog = st.number_input("Cost of Gain ($/lb)", value=0.95)

    # --- PROFIT CALCULATOR (VOG - COG = ROG) ---
    st.title(f"📊 {selected_sex} Analysis")
    calc_df = sex_df[sex_df['frame_muscle'] == selected_grade].sort_values('avg_weight')

    if not calc_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            buy_row = calc_df.iloc[0]
            buy_val = (float(buy_row['avg_price'])/100) * float(buy_row['avg_weight'])
            st.metric("Buy Price", f"${buy_row['avg_price']}")
            st.caption(f"Weight: {buy_row['avg_weight']} lbs")
        
        with col2:
            sell_row = calc_df.iloc[-1]
            sell_val = (float(sell_row['avg_price'])/100) * float(sell_row['avg_weight'])
            st.metric("Sell Price", f"${sell_row['avg_price']}")
            st.caption(f"Weight: {sell_row['avg_weight']} lbs")

        st.divider()
        gain = float(sell_row['avg_weight']) - float(buy_row['avg_weight'])
        if gain > 0:
            vog = (sell_val - buy_val) / gain
            rog = vog - cog
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Value of Gain", f"${vog:.2f}")
            m2.metric("Return on Gain", f"${rog:.2f}", delta=f"${rog:.2f}")
            m3.metric("Net / Head", f"${(rog * gain):,.2f}")
    else:
        st.warning("No weight brackets found for this specific grade.")
else:
    st.error(f"System Offline: {status}")
