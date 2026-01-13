import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

# --- CONFIG & THEME ---
st.set_page_config(page_title="OKC Correlator Pro", layout="wide")
API_KEY = 'pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y'

# --- DATA ENGINE ---
@st.cache_data(ttl=3600)
def get_verified_market_data():
    url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(API_KEY, ''), timeout=15)
        results = response.json().get('results', [])
        if not results: return None, "Report is currently empty."

        # Tiered Mapping: Prevents 'N/A' by searching all known USDA aliases
        clean_rows = []
        for r in results:
            sex = r.get('class') or r.get('animal_class') or 'N/A'
            grade = r.get('frame_muscle') or r.get('grade') or r.get('quality_grade') or 'N/A'
            price = r.get('avg_price') or r.get('price')
            weight = r.get('avg_weight') or r.get('avg_wgt')

            if price and weight:
                clean_rows.append({
                    'date': r.get('report_begin_date', 'Unknown'),
                    'sex': str(sex).strip(),
                    'grade': str(grade).strip(),
                    'range': str(r.get('wgt_range', 'N/A')),
                    'avg_wgt': float(weight),
                    'price': float(price)
                })
        
        df = pd.DataFrame(clean_rows)
        # Always use the most recent date found in the results
        latest = df['date'].iloc[0]
        return df[df['date'] == latest], latest
    except Exception as e:
        return None, f"Network Error: {e}"

# --- USER INTERFACE ---
df, market_date = get_verified_market_data()

if df is not None:
    with st.sidebar:
        st.header("🐄 1. Livestock")
        c_sex = st.selectbox("Type", sorted(df['sex'].unique()))
        
        # Filtering Grade based on Sex
        sex_df = df[df['sex'] == c_sex]
        c_grade = st.selectbox("Grade", sorted(sex_df['grade'].unique()))
        
        st.header("🚜 2. Production")
        adg = st.slider("ADG (lbs/day)", 0.5, 4.0, 2.0, 0.1)
        cog = st.number_input("Cost of Gain ($/lb)", value=0.95)

    st.title("📈 OKC Production & Price Correlator")
    st.success(f"Market Verified: {market_date}")

    # Core Logic
    final_df = sex_df[sex_df['grade'] == c_grade].sort_values('avg_wgt')
    
    if not final_df.empty:
        weight_map = {f"{row['range']} lbs (Avg: {int(row['avg_wgt'])})": row for _, row in final_df.iterrows()}
        
        c1, c2 = st.columns(2)
        with c1:
            p_data = weight_map[st.selectbox("Purchase Weight:", list(weight_map.keys()), index=0)]
            st.metric("Buy Price", f"${p_data['price']:.2f}")
        with c2:
            s_data = weight_map[st.selectbox("Sale Weight:", list(weight_map.keys()), index=len(weight_map)-1)]
            st.metric("Sell Price", f"${s_data['price']:.2f}")

        # Accuracy-Driven Math
        st.divider()
        gain = s_data['avg_wgt'] - p_data['avg_wgt']
        if gain > 0:
            v1, v2 = (p_data['avg_wgt'] * p_data['price']/100), (s_data['avg_wgt'] * s_data['price']/100)
            vog = (v2 - v1) / gain
            rog = vog - cog
            
            r1, r2, r3 = st.columns(3)
            r1.metric("Total Gain", f"{int(gain)} lbs")
            r2.metric("Value of Gain", f"${vog:.2f}", delta=f"${rog:.2f} Margin")
            r3.metric("Net/Head", f"${(rog * gain):,.2f}")
    else:
        st.warning("No specific records for this Grade in the current report.")
else:
    st.error(f"System Error: {market_date}")
