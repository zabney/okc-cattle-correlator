import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

# --- CONFIGURATION ---
st.set_page_config(page_title="OKC Steer/Heifer Profit Correlator", layout="wide")
API_KEY = 'pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y'

# --- DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_verified_feeder_data():
    url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(API_KEY, ''), timeout=15)
        raw_data = response.json().get('results', [])
        
        scrubbed = []
        for r in raw_data:
            # 1. BULLETPROOF CLASS FILTER: Catch all case variations
            raw_class = str(r.get('class', '')).upper()
            is_steer = "STEER" in raw_class
            is_heifer = "HEIFER" in raw_class
            
            if not (is_steer or is_heifer):
                continue
            
            # 2. GRADE EXTRACTION: Focused purely on Feeder Grades
            grade = r.get('frame_muscle')
            price = r.get('avg_price')
            weight = r.get('avg_weight')

            if grade and price and weight:
                scrubbed.append({
                    'report_date': r.get('report_begin_date'),
                    'sex': "Steers" if is_steer else "Heifers",
                    'grade': grade,
                    'range': r.get('wgt_range'),
                    'avg_wgt': float(weight),
                    'price': float(price)
                })
        
        if not scrubbed:
            return None, "No Steer or Heifer data found in the most recent report."
            
        df = pd.DataFrame(scrubbed)
        latest_date = df['report_date'].iloc[0]
        return df[df['report_date'] == latest_date], latest_date
    except Exception as e:
        return None, f"Connection Issue: {e}"

# --- USER INTERFACE ---
df, market_date = get_verified_feeder_data()

if df is not None:
    with st.sidebar:
        st.title("🚜 Market Settings")
        sex_choice = st.radio("1. Select Animal Type", ["Steers", "Heifers"])
        df_sex = df[df['sex'] == sex_choice]
        
        grade_choice = st.selectbox("2. Select Feeder Grade", sorted(df_sex['grade'].unique()))
        
        st.divider()
        st.title("💰 Production Costs")
        adg = st.slider("Target ADG (lbs/day)", 0.5, 4.0, 2.2, 0.1)
        cog = st.number_input("Cost of Gain ($/lb)", value=0.95, step=0.05)

    st.title(f"📈 {sex_choice} Profit & VOG Correlator")
    st.info(f"Verified OKC Data: {market_date}")

    # FILTER DATA FOR CALCULATION
    final = df_sex[df_sex['grade'] == grade_choice].sort_values('avg_wgt')

    if not final.empty:
        # --- CALCULATION DASHBOARD ---
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("📥 Purchase Point")
            p_label = st.selectbox("Buy Weight Bracket", list(final['range']), index=0)
            p_row = final[final['range'] == p_label].iloc[0]
            p_val = (p_row['price'] / 100) * p_row['avg_wgt']
            st.metric("Purchase Price", f"${p_row['price']:.2f}")
            st.caption(f"Avg Weight: {int(p_row['avg_wgt'])} lbs | Total: ${p_val:,.2f}")

        with c2:
            st.subheader("📤 Sale Point")
            s_label = st.selectbox("Projected Sale Bracket", list(final['range']), index=len(final)-1)
            s_row = final[final['range'] == s_label].iloc[0]
            s_val = (s_row['price'] / 100) * s_row['avg_wgt']
            st.metric("Sale Price", f"${s_row['price']:.2f}")
            st.caption(f"Avg Weight: {int(s_row['avg_wgt'])} lbs | Total: ${s_val:,.2f}")

        # --- THE VOG-COG-ROG ENGINE ---
        st.divider()
        gain = s_row['avg_wgt'] - p_row['avg_wgt']
        
        if gain > 0:
            # VOG = (Total Sale Value - Total Buy Value) / Lbs Gained
            vog = (s_val - p_val) / gain
            # ROG = Value of Gain - Cost of Gain
            rog = vog - cog
            net_profit = rog * gain
            days_on_feed = gain / adg

            res1, res2, res3 = st.columns(3)
            res1.metric("Value of Gain (VOG)", f"${vog:.2f}/lb")
            res2.metric("Return on Gain (ROG)", f"${rog:.2f}/lb", 
                       delta=f"${rog:.2f}", delta_color="normal")
            res3.metric("Net Profit / Head", f"${net_profit:,.2f}")
            
            st.warning(f"💡 At {adg} lbs/day, this turn requires **{int(days_on_feed)} days**.")
        else:
            st.error("Select a Sale Weight higher than the Purchase Weight.")
    else:
        st.error("No data available for this grade combination.")
else:
    st.error(f"Error: {market_date}")
