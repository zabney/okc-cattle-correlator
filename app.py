import streamlit as st
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth

st.set_page_config(page_title="OKC Multi-Class Correlator", layout="wide")
API_KEY = 'pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y'

@st.cache_data(ttl=3600)
def get_clean_data():
    url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        response = requests.get(url, auth=HTTPBasicAuth(API_KEY, ''), timeout=15)
        raw = response.json().get('results', [])
        
        scrubbed = []
        for r in raw:
            # --- THE RATIONALE LOGIC ---
            # 1. Start with Feeder Grade
            grade_val = r.get('frame_muscle')
            
            # 2. If no Feeder Grade, check Slaughter Grade + Dressing
            if not grade_val or grade_val == "N/A":
                base_grade = r.get('grade') or "Standard"
                dress = r.get('dressing')
                grade_val = f"{base_grade} ({dress})" if dress else base_grade
                
            # 3. If still nothing, check Replacement Age/Stage
            if grade_val == "Standard":
                age = r.get('age')
                stage = r.get('stage')
                if age: grade_val = f"{age} / {stage}" if stage else age

            # Final check: Price and Weight must exist
            p, w = r.get('avg_price'), r.get('avg_weight')
            if p and w:
                scrubbed.append({
                    'date': r.get('report_begin_date'),
                    'group': r.get('group') or 'Feeder Cattle',
                    'sex': r.get('class') or 'N/A',
                    'grade': grade_val,
                    'avg_wgt': float(w),
                    'price': float(p),
                    'range': r.get('wgt_range')
                })
        
        df = pd.DataFrame(scrubbed)
        latest = df['date'].iloc[0]
        return df[df['date'] == latest], latest
    except:
        return None, "Connection Error"

# --- UI INTERFACE ---
df, market_date = get_clean_data()

if df is not None:
    with st.sidebar:
        st.header("1. Selection")
        # Narrow down by Category (Feeder vs Slaughter)
        cat = st.selectbox("Category", sorted(df['group'].unique()))
        df_cat = df[df['group'] == cat]
        
        # Narrow down by Sex (Steer vs Cow)
        sex = st.selectbox("Sex", sorted(df_cat['sex'].unique()))
        df_sex = df_cat[df_cat['sex'] == sex]
        
        # Narrow down by Grade (The logic fix)
        grade = st.selectbox("Grade / Dressing", sorted(df_sex['grade'].unique()))
        
        st.divider()
        st.header("2. Costs")
        adg = st.slider("ADG", 0.5, 4.0, 2.0)
        cog = st.number_input("Cost of Gain", value=0.95)

    st.title("📊 OKC Cattle Correlator")
    st.info(f"Using OKC Report from {market_date}")

    # Calculation logic...
    final = df_sex[df_sex['grade'] == grade].sort_values('avg_wgt')
    if not final.empty:
        # (Weights and Math logic goes here)
        st.dataframe(final[['range', 'avg_wgt', 'price']], hide_index=True)
