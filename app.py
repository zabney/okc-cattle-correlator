import streamlit as st
import pandas as pd
import requests
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
st.set_page_config(page_title="OKC Cattle Profit Correlator", layout="wide")

# --- DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_verified_data():
    api_url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        # Authentication using your provided API Key
        response = requests.get(api_url, auth=HTTPBasicAuth('pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y', ''), timeout=15)
        raw_json = response.json().get('results', [])
        
        if not raw_json:
            return None, "USDA report is currently empty."
        
        scrubbed = []
        for r in raw_json:
            # DEFENSIVE GET: Prevents 'KeyError' if fields are missing
            raw_class = str(r.get('class', 'UNKNOWN')).upper()
            
            # Fuzzy filter for Steers and Heifers
            if "STEER" in raw_class or "HEIFER" in raw_class:
                grade = r.get('frame_muscle') or r.get('grade') or "UNGRADED"
                price = r.get('avg_price')
                weight = r.get('avg_weight')

                if price and weight:
                    scrubbed.append({
                        'sex': "Steers" if "STEER" in raw_class else "Heifers",
                        'grade': str(grade).upper(),
                        'avg_weight': float(weight),
                        'avg_price': float(price),
                        'wgt_range': r.get('wgt_range', 'N/A')
                    })
        
        if not scrubbed:
            return None, "No Steer/Heifer data found in the latest report."
            
        return pd.DataFrame(scrubbed), "Success"
    except Exception as e:
        return None, f"System Connection Error: {str(e)}"

# --- APP EXECUTION ---
data, status = fetch_verified_data()

if data is not None:
    # --- SIDEBAR ---
    with st.sidebar:
        st.header("1. Filter Market")
        selected_sex = st.radio("Select Type", ["Steers", "Heifers"])
        sex_df = data[data['sex'] == selected_sex]
        
        grade_options = sorted(sex_df['grade'].unique())
        selected_grade = st.selectbox("Select Grade", grade_options)
        
        st.divider()
        st.header("2. Set Costs")
        adg = st.slider("Target ADG (lbs/day)", 0.5, 4.0, 2.2)
        cog = st.number_input("Cost of Gain ($/lb)", value=0.95, step=0.05)

    # --- MAIN DASHBOARD ---
    st.title(f"📊 {selected_sex} Profit Analysis")
    st.caption(f"Status: {status} | Data from Oklahoma National Stockyards")

    calc_df = sex_df[sex_df['grade'] == selected_grade].sort_values('avg_weight')

    if not calc_df.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📥 Purchase")
            p_label = st.selectbox("Buy Weight Bracket", list(calc_df['wgt_range']), index=0)
            p_row = calc_df[calc_df['wgt_range'] == p_label].iloc[0]
            p_val = (p_row['avg_price'] / 100) * p_row['avg_weight']
            st.metric("Purchase $/cwt", f"${p_row['avg_price']:.2f}")
            st.write(f"Weight: {int(p_row['avg_weight'])} lbs | Total: ${p_val:,.2f}")

        with col2:
            st.subheader("📤 Sale")
            s_label = st.selectbox("Sale Weight Bracket", list(calc_df['wgt_range']), index=len(calc_df)-1)
            s_row = calc_df[calc_df['wgt_range'] == s_label].iloc[0]
            s_val = (s_row['avg_price'] / 100) * s_row['avg_weight']
            st.metric("Sale $/cwt", f"${s_row['avg_price']:.2f}")
            st.write(f"Weight: {int(s_row['avg_weight'])} lbs | Total: ${s_val:,.2f}")

        # --- THE VOG-COG-ROG CALCULATION ---
        st.divider()
        gain = s_row['avg_weight'] - p_row['avg_weight']
        
        if gain > 0:
            vog = (s_val - p_val) / gain
            rog = vog - cog
            net_profit = rog * gain
            days = gain / adg

            m1, m2, m3 = st.columns(3)
            m1.metric("Value of Gain (VOG)", f"${vog:.2f}/lb")
            m2.metric("Return on Gain (ROG)", f"${rog:.2f}/lb", delta=f"${rog:.2f}")
            m3.metric("Net Profit / Head", f"${net_profit:,.2f}")
            
            st.info(f"📅 Production Estimate: **{int(days)} days** on feed at {adg} lbs/day.")
        else:
            st.warning("Please select a sale weight higher than the purchase weight.")
    else:
        st.error("No weight data found for this specific grade.")
else:
    st.error(f"App Offline: {status}")
