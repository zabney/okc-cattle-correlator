import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="OKC Steer & Heifer Correlator", layout="wide")
API_KEY = 'pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y'

@st.cache_data(ttl=3600)
def get_feeder_data():
    url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(API_KEY, ''), timeout=15)
        raw = response.json().get('results', [])
        
        scrubbed = []
        for r in raw:
            sex = r.get('class')
            # 1. Eliminate everything except Steers and Heifers
            if sex not in ["Steers", "Heifers"]:
                continue
                
            grade = r.get('frame_muscle')
            price = r.get('avg_price')
            weight = r.get('avg_weight')

            if grade and price and weight:
                scrubbed.append({
                    'date': r.get('report_begin_date'),
                    'sex': sex,
                    'grade': grade,
                    'range': r.get('wgt_range'),
                    'avg_wgt': float(weight),
                    'price': float(price)
                })
        
        df = pd.DataFrame(scrubbed)
        latest = df['date'].iloc[0]
        return df[df['date'] == latest], latest
    except:
        return None, "Connection Error"

# --- SIDEBAR: SIMPLE SELECTION ---
df, market_date = get_feeder_data()

if df is not None:
    with st.sidebar:
        st.header("1. Selection")
        # Only two choices now: Steer or Heifer
        sex_choice = st.radio("Animal Class", ["Steers", "Heifers"])
        df_sex = df[df['sex'] == sex_choice]
        
        # Specific Feeder Grade (e.g., Medium & Large 1)
        grade_choice = st.selectbox("Feeder Grade", sorted(df_sex['grade'].unique()))
        
        st.divider()
        st.header("2. Production")
        adg = st.slider("ADG (lbs/day)", 0.5, 4.0, 2.2, 0.1)
        cog = st.number_input("Cost of Gain ($/lb)", value=0.95, step=0.05)

    # --- MAIN DASHBOARD ---
    st.title(f"📈 {sex_choice} Profit Correlator")
    st.caption(f"Latest OKC Data: {market_date}")

    final = df_sex[df_sex['grade'] == grade_choice].sort_values('avg_wgt')

    if not final.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📥 Purchase")
            p_label = st.selectbox("Buy Weight Bracket", list(final['range']), index=0)
            p_row = final[final['range'] == p_label].iloc[0]
            p_val = (p_row['price'] / 100) * p_row['avg_wgt']
            st.metric("Purchase Price", f"${p_row['price']:.2f}")
            st.write(f"Buy Weight: {int(p_row['avg_wgt'])} lbs")
            st.write(f"Total Buy: ${p_val:,.2f}")

        with col2:
            st.subheader("📤 Sale")
            s_label = st.selectbox("Sale Weight Bracket", list(final['range']), index=len(final)-1)
            s_row = final[final['range'] == s_label].iloc[0]
            s_val = (s_row['price'] / 100) * s_row['avg_wgt']
            st.metric("Sale Price", f"${s_row['price']:.2f}")
            st.write(f"Sale Weight: {int(s_row['avg_wgt'])} lbs")
            st.write(f"Total Sale: ${s_val:,.2f}")

        # --- THE VOG - COG = ROG CALCULATION ---
        st.divider()
        gain = s_row['avg_wgt'] - p_row['avg_wgt']
        
        if gain > 0:
            # Value of Gain (The actual value of the added weight)
            vog = (s_val - p_val) / gain
            # Return on Gain (Profit per pound)
            rog = vog - cog
            net = rog * gain
            days = gain / adg

            res1, res2, res3 = st.columns(3)
            res1.metric("Value of Gain (VOG)", f"${vog:.2f}")
            res2.metric("Return on Gain (ROG)", f"${rog:.2f}", delta=f"${rog:.2f}")
            res3.metric("Net Profit / Head", f"${net:,.2f}")
            
            st.info(f"📅 This program requires **{int(days)} days** at an ADG of {adg}.")
        else:
            st.warning("Please select a sale weight higher than the purchase weight.")
    else:
        st.error("No data found for this grade.")
